# The order pipeline: the only place that knows the order of the steps.
#   1 stock (GET) -> 2 solve length (or use the ordered length) -> 3 validate -> 4 params.json -> 5 mass + stock check
#   -> 6 CAD 3MF -> 7 simulate -> 8 register use (PUT) -> 9 report.json
# Every outcome is a result (produced / rejected / postponed), never a crash.
# Use of AI: generated with AI assistance (Claude), checked by the group (tests/test_orders.py).

import json
import time
from dataclasses import asdict, dataclass, field, fields, replace
from enum import Enum
from pathlib import Path

from .params import PRINT_PARTS, Filament, KitInputs, load_printer, validate
from .physics import filament_g, length_range, part_list, period, period_range, solve_length
from .stock import StockError, check_stock

OUTPUT = Path(__file__).resolve().parent.parent / "output"


@dataclass
class Order:
    order_id: str
    customer: str
    target_period_s: float | None = None        # give EITHER a period ...
    pendulum_length_mm: float | None = None     # ... OR a pendulum length (axle -> weight centre)
    weightDiameter: float = 30
    weightHeight: float = 30
    infill: float = 0.15
    wall_loops: int = 2
    spool_ids: dict = field(default_factory=dict)   # part -> spool id, parts = params.PRINT_PARTS

    @classmethod
    def from_dict(cls, d):  # ignores fields that older versions of the program saved
        names = {f.name for f in fields(cls)}
        return cls(**{key: val for key, val in d.items() if key in names})


class Status(str, Enum):
    PRODUCED = "produced"
    REJECTED = "rejected"      # can never be made as ordered
    POSTPONED = "postponed"    # try again later (stock down, too little filament, missing software)


def base_inputs(order=None, printer=None):
    p = printer or load_printer()
    k = KitInputs(xPrint=p["x_mm"], yPrint=p["y_mm"], zPrint=p["z_mm"])
    if order is not None:
        k = replace(k, order_id=order.order_id, target_period_s=order.target_period_s,
                    weightDiameter=order.weightDiameter, weightHeight=order.weightHeight,
                    infill=order.infill, wall_loops=order.wall_loops)
    return k


# What can be ordered on this printer (shown on the order form)
def order_limits(printer=None, weightDiameter=30):
    k = replace(base_inputs(printer=printer), weightDiameter=weightDiameter)
    lmin, lmax = length_range(k)
    tmin, tmax = period_range(k)
    return {"printer": printer or load_printer(), "period_s": (tmin, tmax), "length_mm": (lmin, lmax),
            "weight_mm": (15, min(k.xPrint, k.yPrint) - 12.5 * 2 - k.weightTolerance * 2), "kit_height_mm": k.zPrint}


# Checked BEFORE an order is accepted: must fit the printer (no stock needed)
def check_order(order, printer=None):
    if (order.target_period_s is None) == (order.pendulum_length_mm is None):
        return ["Choose either a swing period or a pendulum length."]
    lim = order_limits(printer, order.weightDiameter)
    w0, w1 = lim["weight_mm"]
    if not w0 <= order.weightDiameter <= w1:
        return [f"Weight diameter must be {w0:.0f}-{w1:.0f} mm."]
    problems = []
    t0, t1 = lim["period_s"]
    l0, l1 = lim["length_mm"]
    if order.target_period_s is not None and not t0 <= order.target_period_s <= t1:
        problems.append(f"The period must be {t0:.3f}-{t1:.3f} s to fit the printer.")
    if order.pendulum_length_mm is not None and not l0 <= order.pendulum_length_mm <= l1:
        problems.append(f"The pendulum length must be {l0:.1f}-{l1:.1f} mm to fit the printer.")
    if not 0 <= order.infill <= 1:
        problems.append("Infill must be 0-100 %.")
    if order.wall_loops < 1:
        problems.append("Wall loops must be at least 1.")
    return problems


def to_inputs(order, spools, printer=None):
    k = base_inputs(order, printer)
    for part in PRINT_PARTS:
        s = spools.get(order.spool_ids.get(part))
        if s is None:
            raise KeyError(f"no valid spool chosen for '{part}'")
        k.filaments[part] = Filament(s.spool_id, s.name, s.material, s.density_g_cm3, s.color_hex)
    return k


def process_order(order, stock, out_root=OUTPUT, make_cad=True, run_sim=True, printer=None):
    out = Path(out_root) / order.order_id
    out.mkdir(parents=True, exist_ok=True)
    rep = {"order_id": order.order_id, "customer": order.customer, "target_period_s": order.target_period_s,
           "ordered_length_mm": order.pendulum_length_mm}

    def finish(status, reason):
        rep.update(status=status.value, reason=reason, time=time.strftime("%Y-%m-%d %H:%M:%S"))
        (out / "report.json").write_text(json.dumps(rep, indent=2))
        return rep

    # 1 stock
    try:
        spools = stock.spools()
    except StockError as e:
        return finish(Status.POSTPONED, f"material stock not available: {e}")
    try:
        k = to_inputs(order, spools, printer)
    except KeyError as e:
        return finish(Status.REJECTED, str(e.args[0]))

    # 2 pendulum length: solved from the period, or taken from the order
    if (order.target_period_s is None) == (order.pendulum_length_mm is None):
        return finish(Status.REJECTED, "give either a period or a pendulum length")
    if order.target_period_s is not None:
        sol = solve_length(k)
        k, T_formula, message = sol.inputs, sol.period_s, sol.message
        rep["error_to_target_ms"] = round(sol.error_ms, 3)
        if not sol.feasible:
            rep.update(pendelumLenght_mm=k.pendelumLenght, period_formula_s=round(T_formula, 5))
            return finish(Status.REJECTED, message)
    else:
        lo, hi = length_range(k)
        k = replace(k, pendelumLenght=order.pendulum_length_mm)
        T_formula = period(k).period_s
        message = (f"pendelumLenght {k.pendelumLenght:.2f} mm gives T = {T_formula:.4f} s. "
                   f"Possible lengths with this weight on this printer: {lo:.1f}-{hi:.1f} mm.")
        if not lo <= k.pendelumLenght <= hi:
            return finish(Status.REJECTED, f"pendulum length {k.pendelumLenght} mm is outside the possible "
                                           f"{lo:.1f}-{hi:.1f} mm")
    rep.update(pendelumLenght_mm=k.pendelumLenght, period_formula_s=round(T_formula, 5))

    # 3 validate
    problems = validate(k)
    if problems:
        return finish(Status.REJECTED, "; ".join(problems))

    # 4 the shared parameter file
    k.save(out / "params.json")

    # 5 mass + stock check
    use = filament_g(k)
    rep["masses_g"] = {p.name: round(p.mass_g, 2) for p in part_list(k)}
    rep["filament_g"] = {p: round(g, 2) for p, g in use.items()}
    per_spool = {}
    for part, grams in use.items():
        sid = k.filaments[part].spool_id
        per_spool[sid] = per_spool.get(sid, 0) + grams
    lack = check_stock(per_spool, spools)
    if lack:
        return finish(Status.POSTPONED, "not enough material: " + "; ".join(lack))

    # 6 CAD -> 3MF
    if make_cad:
        try:
            from .cad import export_3mf
        except ImportError:
            return finish(Status.POSTPONED, "CadQuery is not installed")
        rep["files"] = [p.name for p in export_3mf(k, out)]

    # 7 simulation (MuJoCo) with the same parameters
    T = T_formula
    if run_sim:
        try:
            from .simulation import save_plot, simulate
            sim = simulate(k)
            save_plot(k, sim, out / "swing.png")
            T = sim.period_s
            rep.update(period_simulated_s=round(sim.period_s, 5),
                       difference_ms=round((sim.period_s - T_formula) * 1000, 3))
        except ImportError:
            rep["simulation"] = "skipped: MuJoCo is not installed"
    rep["frequency_hz"] = round(1 / T, 4)

    # 8 register filament use, only when everything above worked
    try:
        for sid, grams in per_spool.items():
            stock.use(sid, grams)
    except StockError as e:
        return finish(Status.POSTPONED, f"could not register filament use: {e}")

    # 9 report
    return finish(Status.PRODUCED, message)


def save_order(order, folder):
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / f"{order.order_id}.json").write_text(json.dumps(asdict(order), indent=2))


def load_orders(path):
    data = json.loads(Path(path).read_text())
    return [Order.from_dict(d) for d in (data if isinstance(data, list) else [data])]




