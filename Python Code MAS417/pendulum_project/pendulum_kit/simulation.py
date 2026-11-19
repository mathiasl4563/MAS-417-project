# MuJoCo simulation of the kit, built from the same KitInputs as the CAD and the formula.
# Run alone:  python -m pendulum_kit.simulation [--length 150 --infill 100 --amplitude 45 --no-view]
#             macOS: mjpython -m pendulum_kit.simulation
# Viewer:     left-drag rotate | right-drag move | scroll zoom | Space pause
#             Simulation > Load key: back to the release angle (Reset = hanging still)
#             double-click weight + Ctrl+right-drag push | Ctrl+P screenshot
# Axes as in the CAD: Z up, axle along X, swing in the YZ plane.
# Use of AI: generated with AI assistance (Claude), checked by the group.

import argparse
import json
import math
from types import SimpleNamespace

import mujoco
import mujoco.viewer
import numpy as np

from .params import CadValidationError, KitInputs, derive, validate_or_raise
from .physics import part_list, period


def build_mjcf(k):
    g = derive(k)
    mm, p = 1e-3, {x.name: x for x in part_list(k, g)}
    a, t = k.pendelumArmBaseThickness, k.pendelumArmArmThickness

    def geom(name, typ, size, pos, rgba, mass=None, extra=""):
        s = " ".join(f"{v * mm:.6g}" for v in size)
        q = " ".join(f"{v * mm:.6g}" for v in pos)
        m = f' mass="{mass / 1000:.6g}"' if mass is not None else ""
        return f'<geom name="{name}" type="{typ}" size="{s}" pos="{q}" rgba="{rgba}" contype="0" conaffinity="0"{m} {extra}/>'

    ph, px = g.pillarHeight, g.squareHoleDistance / 2
    fixed = [geom("base", "cylinder", (g.baseDiameter / 2, k.baseThickness / 2), (0, 0, k.baseThickness / 2), ".6 .6 .6 1")]
    fixed += [geom(f"pillar{i}", "box", (k.squareHoleWidth / 2, k.squareHoleHeight / 2, ph / 2), (s * px, 0, ph / 2),
                   ".2 .4 .9 1") for i, s in enumerate((1, -1))]
    moving = [
        geom("hub", "box", (g.hubLength / 2, a / 2, a / 2), (0, 0, 0), "1 .5 0 1", p["hub"].mass_g),
        geom("axle", "cylinder", (k.axleDiameter / 2, g.axleLength / 2), (0, 0, 0), ".3 .3 .3 1",
             p["axle"].mass_g, 'euler="0 90 0"'),
        geom("arm", "box", (t / 2, a / 2, g.armLength / 2), (0, 0, -p["arm"].z), "1 .5 0 1", p["arm"].mass_g),
        geom("weight", "cylinder", (k.weightDiameter / 2, k.weightHeight / 2), (0, 0, -p["weight"].z),
             ".9 .1 .1 1", p["weight"].mass_g),
    ]
    nl = "\n      "
    return f"""<mujoco model="pendulum_kit">
  <option gravity="0 0 -9.81" timestep="0.0002" integrator="RK4"/>
  <worldbody>
    <light pos="0 -0.5 0.6" dir="0 0.5 -0.6"/>
    {nl.join(fixed)}
    <body name="pendulum" pos="0 0 {g.axleZ * mm:.6g}">
      <joint name="hinge" type="hinge" axis="1 0 0" damping="{k.damping}"/>
      {nl.join(moving)}
    </body>
  </worldbody>
  <keyframe><key name="release" qpos="{math.radians(k.amplitude_deg):.6g}"/></keyframe>
</mujoco>"""


def make_model(k):
    validate_or_raise(k)
    model = mujoco.MjModel.from_xml_string(build_mjcf(k))
    data = mujoco.MjData(model)
    data.qpos[0] = math.radians(k.amplitude_deg)
    return model, data


# Period = mean time between upward zero crossings
def period_from_trace(t, th):
    i = np.where((th[:-1] < 0) & (th[1:] >= 0))[0]
    if len(i) < 2:
        return float("nan")
    crossings = t[i] - th[i] * (t[i + 1] - t[i]) / (th[i + 1] - th[i])
    return float(np.mean(np.diff(crossings)))


# Steps the model from the release angle and records the angle
def simulate(k, duration_s=8.0):
    model, data = make_model(k)
    n = int(duration_s / model.opt.timestep)
    t, th = np.empty(n), np.empty(n)
    for i in range(n):
        mujoco.mj_step(model, data)
        t[i], th[i] = data.time, data.qpos[0]
    T = period_from_trace(t, th)
    return SimpleNamespace(t=t, theta=th, period_s=T, frequency_hz=1 / T)


def save_plot(k, sim, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(sim.t, np.degrees(sim.theta))
    ax.set(xlabel="time [s]", ylabel="angle [deg]",
           title=f"L={k.pendelumLenght:.1f} D={k.weightDiameter} h={k.weightHeight} mm, infill {k.infill:.0%}: "
                 f"T={sim.period_s:.4f} s, f={sim.frequency_hz:.3f} Hz")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# Opens the MuJoCo 3D viewer at the release angle (blocks until the window is closed)
def view(k):
    model, data = make_model(k)
    mujoco.viewer.launch(model, data)


def main():
    ap = argparse.ArgumentParser(description="Simulate the pendulum kit in MuJoCo")
    for flag, default, text in [("length", 100, "pendelumLenght [mm]"), ("diameter", 30, "weightDiameter [mm]"),
                                ("height", 30, "weightHeight [mm]"), ("infill", 15, "infill [%%]"),
                                ("density", 1.24, "filament density [g/cm3]"), ("amplitude", 45, "release angle [deg]"),
                                ("damping", 0.0, "axle damping [N m s/rad]"), ("duration", 8.0, "simulated time [s]")]:
        ap.add_argument(f"--{flag}", type=float, default=default, help=text)
    ap.add_argument("--plot", default="pendulum_sim.png", help="plot file ('' = no plot)")
    ap.add_argument("--json", default="pendulum_result.json", help="result file ('' = none)")
    ap.add_argument("--no-view", action="store_true", help="do not open the 3D viewer")
    a = ap.parse_args()

    k = KitInputs(pendelumLenght=a.length, weightDiameter=a.diameter, weightHeight=a.height, infill=a.infill / 100,
                  amplitude_deg=a.amplitude, damping=a.damping)
    for f in k.filaments.values():
        f.density_g_cm3 = a.density
    try:
        sim = simulate(k, a.duration)
    except CadValidationError as e:
        raise SystemExit("Invalid inputs:\n  - " + "\n  - ".join(e.problems))
    f = period(k)
    result = {"masses_g": {p.name: round(p.mass_g, 2) for p in part_list(k)},
              "swinging_mass_g": round(f.mass_g, 2), "d_cm_mm": round(f.d_mm, 2),
              "period_formula_s": round(f.period_s, 5), "period_simulated_s": round(sim.period_s, 5),
              "frequency_simulated_hz": round(sim.frequency_hz, 4),
              "difference_ms": round((sim.period_s - f.period_s) * 1000, 3)}
    for key, val in result.items():
        print(f"{key:24s} {val}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"inputs": {"pendelumLenght": k.pendelumLenght, "weightDiameter": k.weightDiameter,
                                  "weightHeight": k.weightHeight, "infill": k.infill,
                                  "amplitude_deg": k.amplitude_deg}, **result}, fh, indent=2)
        print("Saved", a.json)
    if a.plot:
        save_plot(k, sim, a.plot)
        print("Saved", a.plot)
    if not a.no_view:
        view(k)


if __name__ == "__main__":
    main()
