# Simulates the pendulum kit in MuJoCo with the same inputs and geometry as pendulum_cad.py.
# Use of AI: generated with AI assistance (Claude), checked by the group.
#
# Install:  pip install numpy matplotlib mujoco
# Run:      python pendulum_sim.py [--length 150 --infill 100 --amplitude 45 --no-view ...]
#           (python pendulum_sim.py -h lists all options)
#           macOS: mjpython pendulum_sim.py
# Output:   periods in the terminal, pendulum_sim.png (angle vs time), then the MuJoCo 3D viewer.
# Viewer:   left-drag rotate | right-drag move | scroll zoom | Space pause
#           Simulation > Load key: back to the release angle (Reset = hanging still)
#           double-click weight + Ctrl+right-drag push | Ctrl+P screenshot
# Axes as in the CAD: Z up, axle along X, swing in the YZ plane. Units: mm, g, s.

import argparse
import math
from dataclasses import dataclass
from types import SimpleNamespace

import mujoco
import mujoco.viewer
import numpy as np

G = 9.81

@dataclass
class KitInputs:
    # Same names and values as the CAD
    pendelumLenght: float = 100
    weightDiameter: float = 30
    weightHeight: float = 30
    xPrint: float = 256
    yPrint: float = 256
    zPrint: float = 256
    squareTolerance: float = 0.2
    circleTolerance: float = 0.5
    axleTolerance: float = 0.5
    weightTolerance: float = 5
    WeightDistanceTolerance: float = 5
    squareHoleHeight: float = 20
    squareHoleWidth: float = 5
    baseThickness: float = 5
    axleDistanceFromTop: float = 5
    axleDiameter: float = 5
    axleCuttof: float = 5
    pendelumArmBaseThickness: float = 10
    pendelumArmArmThickness: float = 5
    # Material, print settings, simulation
    density_g_cm3: float = 1.24
    infill: float = 0.15
    wall_loops: int = 2
    line_width_mm: float = 0.42
    top_bottom_layers: int = 4
    layer_height_mm: float = 0.2
    amplitude_deg: float = 45.0
    damping: float = 0.0  # keep tiny, e.g. 0.000005


class CadValidationError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


# Derived values and checks, same formulas as pendulum_cad.py
def derive(k):
    L, h, D = k.pendelumLenght, k.weightHeight, k.weightDiameter
    problems = []
    if D < 15:
        problems.append("Error: weightDiameter is too small, minimum 15mm")
    if D > k.xPrint - 12.5 * 2 - k.weightTolerance * 2:
        problems.append(f"Error: weightDiameter is too large, maximum {k.xPrint - 12.5 * 2 - k.weightTolerance * 2}mm")
    shd = max(D + k.weightTolerance * 2 + k.squareHoleWidth, 50)
    wdb = math.sqrt((L + h / 2) ** 2 + (D / 2) ** 2) + k.WeightDistanceTolerance - L - h / 2
    pillar = k.baseThickness + L + wdb + k.axleDistanceFromTop + h / 2
    if pillar > k.zPrint:
        problems.append("Error: pillars are outside the base")
    if problems:
        raise CadValidationError(problems)
    return SimpleNamespace(
        squareHoleDistance=shd, baseDiameter=shd + 20, weightDistanseToBase=wdb,
        pillarHeight=pillar, axleZ=pillar - k.axleDistanceFromTop,
        hubLength=shd - k.squareHoleWidth - k.axleTolerance * 2,
        axleLength=2 * ((shd + 20) / 2 - k.axleCuttof),
        armLength=L + h / 2 - k.pendelumArmBaseThickness / 2,
        weightBottomZ=wdb + k.baseThickness)


# Printed mass: solid shell (area x wall thickness) + infill in the rest
def printed_mass_g(v, area, k):
    t = (k.wall_loops * k.line_width_mm + k.top_bottom_layers * k.layer_height_mm) / 2
    shell = min(v, area * t)
    return k.density_g_cm3 / 1000 * (shell + k.infill * (v - shell))


@dataclass
class Body:
    name: str
    mass_g: float
    z_mm: float       # centre of mass, distance below the axle
    i_unit: float     # inertia about own centre (X axis) per unit mass [mm^2]


# Hub (solid, axle fills its hole), axle stubs outside the hub, arm, weight minus slot
def swinging_bodies(k, g):
    a, t, r = k.pendelumArmBaseThickness, k.pendelumArmArmThickness, k.axleDiameter / 2
    R, h, Lb = k.weightDiameter / 2, k.weightHeight, g.armLength
    stub = max(g.axleLength - g.hubLength, 0)
    sx, sy = t + k.squareTolerance, a + k.squareTolerance
    cyl, slot = math.pi * R ** 2 * h, sx * sy * h
    parts = [  # name, volume, area, z, inertia per unit mass
        ("hub", g.hubLength * a * a, 4 * g.hubLength * a + 2 * a * a, 0, a * a / 6),
        ("axle", math.pi * r * r * stub, 2 * math.pi * r * (stub + r), 0, r * r / 2),
        ("arm", t * a * Lb, 2 * (t * a + t * Lb + a * Lb), a / 2 + Lb / 2, (a * a + Lb * Lb) / 12),
        ("weight", cyl - slot,
         2 * (math.pi * R ** 2 - sx * sy) + 2 * math.pi * R * h + 2 * (sx + sy) * h,
         g.axleZ - g.weightBottomZ - h / 2,
         (cyl * (3 * R * R + h * h) - slot * (sy * sy + h * h)) / 12 / (cyl - slot)),
    ]
    return [Body(n, printed_mass_g(v, A, k), z, i) for n, v, A, z, i in parts]


# Physical pendulum: T0 = 2*pi*sqrt(I / (M g d)), plus amplitude correction
def formula_period(bodies, amplitude_deg):
    m = np.array([b.mass_g for b in bodies]) / 1000
    z = np.array([b.z_mm for b in bodies]) / 1000
    M, d = m.sum(), float(m @ z / m.sum())
    I = float(m @ (np.array([b.i_unit for b in bodies]) * 1e-6 + z ** 2))
    th = math.radians(amplitude_deg)
    T = 2 * math.pi * math.sqrt(I / (M * G * d)) * (1 + th ** 2 / 16 + 11 * th ** 4 / 3072)
    return SimpleNamespace(mass_g=M * 1000, d_mm=d * 1000, I=I, period_s=T)


def build_mjcf(k, g, bodies):
    mm, b = 1e-3, {x.name: x for x in bodies}
    a, t = k.pendelumArmBaseThickness, k.pendelumArmArmThickness
    stub = max(g.axleLength - g.hubLength, 0)

    def geom(name, typ, size, pos, rgba, mass=None, extra=""):
        s = " ".join(f"{v * mm:.6g}" for v in size)
        p = " ".join(f"{v * mm:.6g}" for v in pos)
        m = f' mass="{mass / 1000:.6g}"' if mass is not None else ""
        return f'<geom name="{name}" type="{typ}" size="{s}" pos="{p}" rgba="{rgba}" contype="0" conaffinity="0"{m} {extra}/>'

    ph, px = g.pillarHeight, g.squareHoleDistance / 2
    fixed = [geom("base", "cylinder", (g.baseDiameter / 2, k.baseThickness / 2), (0, 0, k.baseThickness / 2), ".6 .6 .6 1")]
    fixed += [geom(f"pillar{i}", "box", (k.squareHoleWidth / 2, k.squareHoleHeight / 2, ph / 2), (s * px, 0, ph / 2),
                   ".2 .4 .9 1") for i, s in enumerate((1, -1))]
    moving = [geom("hub", "box", (g.hubLength / 2, a / 2, a / 2), (0, 0, 0), "1 .5 0 1", b["hub"].mass_g)]
    moving += [geom(f"axle{i}", "cylinder", (k.axleDiameter / 2, stub / 4), (s * (g.hubLength / 2 + stub / 4), 0, 0),
                    ".3 .3 .3 1", b["axle"].mass_g / 2, 'euler="0 90 0"') for i, s in enumerate((1, -1))]
    moving += [geom("arm", "box", (t / 2, a / 2, g.armLength / 2), (0, 0, -b["arm"].z_mm), "1 .5 0 1", b["arm"].mass_g),
               geom("weight", "cylinder", (k.weightDiameter / 2, k.weightHeight / 2), (0, 0, -b["weight"].z_mm),
                    ".9 .1 .1 1", b["weight"].mass_g)]
    return f"""<mujoco model="pendulum_kit">
  <option gravity="0 0 -9.81" timestep="0.0002" integrator="RK4"/>
  <worldbody>
    <light pos="0 -0.5 0.6" dir="0 0.5 -0.6"/>
    {chr(10).join(fixed)}
    <body name="pendulum" pos="0 0 {g.axleZ * mm:.6g}">
      <joint name="hinge" type="hinge" axis="1 0 0" damping="{k.damping}"/>
      {chr(10).join(moving)}
    </body>
  </worldbody>
  <keyframe><key name="release" qpos="{math.radians(k.amplitude_deg):.6g}"/></keyframe>
</mujoco>"""


# Period = mean time between upward zero crossings
def period_from_trace(t, th):
    i = np.where((th[:-1] < 0) & (th[1:] >= 0))[0]
    if len(i) < 2:
        return float("nan")
    crossings = t[i] - th[i] * (t[i + 1] - t[i]) / (th[i + 1] - th[i])
    return float(np.mean(np.diff(crossings)))


def make_model(k):
    g = derive(k)
    model = mujoco.MjModel.from_xml_string(build_mjcf(k, g, swinging_bodies(k, g)))
    data = mujoco.MjData(model)
    data.qpos[0] = math.radians(k.amplitude_deg)
    return model, data


# Steps the MuJoCo model from the release angle and records the angle
def simulate(k, duration_s=8.0):
    model, data = make_model(k)
    n = int(duration_s / model.opt.timestep)
    t, th = np.empty(n), np.empty(n)
    for i in range(n):
        mujoco.mj_step(model, data)
        t[i], th[i] = data.time, data.qpos[0]
    return SimpleNamespace(t=t, theta=th, period_s=period_from_trace(t, th))


# Does everything; use this from Flask (catch CadValidationError)
def run(k, duration_s=8.0):
    g = derive(k)
    bodies = swinging_bodies(k, g)
    f = formula_period(bodies, k.amplitude_deg)
    sim = simulate(k, duration_s)
    return {"masses_g": {b.name: round(b.mass_g, 2) for b in bodies},
            "swinging_mass_g": round(f.mass_g, 2), "d_cm_mm": round(f.d_mm, 2),
            "period_formula_s": f.period_s, "period_simulated_s": sim.period_s,
            "difference_ms": (sim.period_s - f.period_s) * 1000, "_sim": sim}


def save_plot(k, sim, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(sim.t, np.degrees(sim.theta))
    ax.set(xlabel="time [s]", ylabel="angle [deg]",
           title=f"L={k.pendelumLenght} D={k.weightDiameter} h={k.weightHeight} mm, infill {k.infill:.0%}: "
                 f"T_sim={sim.period_s:.4f} s")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Plot saved to {path}")


# Opens the MuJoCo 3D viewer at the release angle (blocks until the window is closed)
def view(k):
    model, data = make_model(k)
    print("Opening the MuJoCo viewer (close the window to finish)...")
    mujoco.viewer.launch(model, data)


def main():
    p = argparse.ArgumentParser(description="Simulate the pendulum kit in MuJoCo")
    for flag, default, text in [("length", 100, "pendelumLenght [mm]"), ("diameter", 30, "weightDiameter [mm]"),
                                ("height", 30, "weightHeight [mm]"), ("infill", 15, "infill [%%]"),
                                ("density", 1.24, "filament density [g/cm3]"), ("amplitude", 45, "release angle [deg]"),
                                ("damping", 0.0, "axle damping [N m s/rad]"), ("duration", 8.0, "simulated time [s]")]:
        p.add_argument(f"--{flag}", type=float, default=default, help=text)
    p.add_argument("--plot", default="pendulum_sim.png", help="plot file ('' = no plot)")
    p.add_argument("--no-view", action="store_true", help="do not open the 3D viewer")
    a = p.parse_args()

    k = KitInputs(pendelumLenght=a.length, weightDiameter=a.diameter, weightHeight=a.height,
                  infill=a.infill / 100, density_g_cm3=a.density, amplitude_deg=a.amplitude, damping=a.damping)
    try:
        r = run(k, a.duration)
    except CadValidationError as e:
        raise SystemExit("Invalid inputs:\n  - " + "\n  - ".join(e.problems))

    print("Masses [g]: " + ", ".join(f"{n} {m}" for n, m in r["masses_g"].items())
          + f"  (swinging total {r['swinging_mass_g']} g)")
    print(f"Pivot -> centre of mass: {r['d_cm_mm']} mm")
    print(f"Period, formula:   {r['period_formula_s']:.4f} s")
    print(f"Period, simulated: {r['period_simulated_s']:.4f} s")
    print(f"Difference:        {r['difference_ms']:+.2f} ms")
    if a.plot:
        save_plot(k, r["_sim"], a.plot)
    if not a.no_view:
        view(k)


if __name__ == "__main__":
    main()