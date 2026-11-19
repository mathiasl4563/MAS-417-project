# Mass of every printed part, the physical-pendulum period, and the solver that picks pendelumLenght.
#   T0 = 2*pi*sqrt(I / (M g d)),  I = sum(I_cm + m r^2),  d = sum(m r) / M   (OpenStax Univ. Physics 1, 15.4)
#   T  = T0 * (1 + th^2/16 + 11 th^4/3072)  for release angle th
# Use of AI: generated with AI assistance (Claude), checked by the group (tests/test_physics.py).

import math
from dataclasses import dataclass, replace

import numpy as np

from .params import derive, validate

G = 9.81


# Printed mass: solid shell (area x wall thickness) + infill in the rest
def printed_mass_g(volume, area, density, k):
    t = (k.wall_loops * k.line_width_mm + k.top_bottom_layers * k.layer_height_mm) / 2
    shell = min(volume, area * t)
    return density / 1000 * (shell + k.infill * (volume - shell))


@dataclass
class Part:
    name: str
    filament: str       # which spool it is printed from (params.PRINT_PARTS)
    volume: float       # mm^3
    area: float         # mm^2
    swings: bool
    z: float = 0.0      # centre of mass below the axle [mm] (swinging parts)
    i_unit: float = 0.0 # inertia about own centre, X axis, per unit mass [mm^2]
    mass_g: float = 0.0


# Same shapes as cad.py, with analytic volume and area
def part_list(k, g=None):
    g = g or derive(k)
    a, t = k.pendelumArmBaseThickness, k.pendelumArmArmThickness
    r, R, h, Lb = k.axleDiameter / 2, k.weightDiameter / 2, k.weightHeight, g.armLength
    T, H = k.baseThickness, g.pillarHeight

    sw, sh = k.squareHoleWidth + k.squareTolerance, k.squareHoleHeight + k.squareTolerance
    Rb = g.baseDiameter / 2
    rh = r + k.circleTolerance
    hub_hole = math.pi * r * r * g.hubLength
    sx, sy = t + k.squareTolerance, a + k.squareTolerance
    cyl, slot = math.pi * R * R * h, sx * sy * h

    parts = [
        Part("base", "base", math.pi * Rb ** 2 * T - 2 * sw * sh * T,
             2 * (math.pi * Rb ** 2 - 2 * sw * sh) + 2 * math.pi * Rb * T + 4 * (sw + sh) * T, False),
        Part("pillars", "pillar", 2 * (k.squareHoleWidth * k.squareHoleHeight * H - math.pi * rh ** 2 * k.squareHoleWidth),
             2 * (2 * (k.squareHoleWidth * k.squareHoleHeight + (k.squareHoleWidth + k.squareHoleHeight) * H)
                  + 2 * math.pi * rh * k.squareHoleWidth - 2 * math.pi * rh ** 2), False),
        Part("axle", "axle", math.pi * r * r * g.axleLength, 2 * math.pi * r * (g.axleLength + r), True, 0, r * r / 2),
        Part("hub", "arm", a * a * g.hubLength - hub_hole,
             4 * a * g.hubLength + 2 * (a * a - math.pi * r * r) + 2 * math.pi * r * g.hubLength, True, 0,
             (a * a * g.hubLength * a * a / 6 - hub_hole * r * r / 2) / (a * a * g.hubLength - hub_hole)),
        Part("arm", "arm", t * a * Lb, 2 * (t * a + t * Lb + a * Lb), True, a / 2 + Lb / 2, (a * a + Lb * Lb) / 12),
        Part("weight", "weight", cyl - slot,
             2 * (math.pi * R * R - sx * sy) + 2 * math.pi * R * h + 2 * (sx + sy) * h, True,
             g.axleZ - g.weightBottomZ - h / 2,
             (cyl * (3 * R * R + h * h) - slot * (sy * sy + h * h)) / 12 / (cyl - slot)),
    ]
    for p in parts:
        p.mass_g = printed_mass_g(p.volume, p.area, k.filaments[p.filament].density_g_cm3, k)
    return parts


# Grams of filament per printed part (hub counted with the arm)
def filament_g(k):
    use = {}
    for p in part_list(k):
        use[p.filament] = use.get(p.filament, 0.0) + p.mass_g
    return use


@dataclass
class Period:
    mass_g: float       # swinging mass
    d_mm: float         # axle -> centre of mass
    I: float            # kg m^2 about the axle
    period_s: float

    @property
    def frequency_hz(self):
        return 1 / self.period_s


def period(k, amplitude_deg=None):
    sw = [p for p in part_list(k) if p.swings]
    m = np.array([p.mass_g for p in sw]) / 1000
    z = np.array([p.z for p in sw]) / 1000
    i = np.array([p.i_unit for p in sw]) * 1e-6
    M = m.sum()
    d = float(m @ z / M)
    I = float(m @ (i + z ** 2))
    th = math.radians(k.amplitude_deg if amplitude_deg is None else amplitude_deg)
    T = 2 * math.pi * math.sqrt(I / (M * G * d)) * (1 + th ** 2 / 16 + 11 * th ** 4 / 3072)
    return Period(float(M * 1000), d * 1000, I, T)


# Bisection: root of f on [lo, hi] where f(lo) and f(hi) have opposite signs
def bisection(f, lo, hi, tol=1e-4):
    f_lo = f(lo)
    while hi - lo > tol:
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return (lo + hi) / 2


# Shortest and longest pendelumLenght that pass validate() (height grows with the length)
def length_range(k):
    lo = k.weightHeight / 2 + k.pendelumArmBaseThickness / 2 + 1
    hi = bisection(lambda L: derive(replace(k, pendelumLenght=L)).pillarHeight - k.zPrint, lo, 1000, tol=1e-3) - 0.01
    return lo, hi


def period_range(k):
    lo, hi = length_range(k)
    return period(replace(k, pendelumLenght=lo)).period_s, period(replace(k, pendelumLenght=hi)).period_s


@dataclass
class Solution:
    inputs: object
    feasible: bool
    period_s: float
    error_ms: float
    message: str


# Finds pendelumLenght that gives k.target_period_s (period grows with the length)
def solve_length(k, tol_ms=5.0):
    lo, hi = length_range(k)
    if hi <= lo:
        return Solution(k, False, float("nan"), float("nan"), "no valid pendelumLenght fits the height limit")
    t_lo, t_hi = period(replace(k, pendelumLenght=lo)).period_s, period(replace(k, pendelumLenght=hi)).period_s
    target = k.target_period_s
    if target < t_lo or target > t_hi:
        L = lo if target < t_lo else hi
    else:
        L = bisection(lambda x: period(replace(k, pendelumLenght=x)).period_s - target, lo, hi)
    best = replace(k, pendelumLenght=round(L, 3))
    T = period(best).period_s
    err = (T - target) * 1000
    problems = validate(best)
    ok = abs(err) <= tol_ms and not problems
    msg = (f"pendelumLenght {best.pendelumLenght:.2f} mm gives T = {T:.4f} s (target {target:.4f} s, "
           f"error {err:+.2f} ms). Possible with this weight on this printer: {t_lo:.3f}-{t_hi:.3f} s.")
    if problems:
        msg += " " + "; ".join(problems)
    return Solution(best, ok, T, err, msg)
