# Whole order pipeline with a fake stock (no Docker, CadQuery or MuJoCo needed)
# Use of AI: generated with AI assistance (Claude), checked by the group.
import json

import pytest

from pendulum_kit.orders import Order, process_order
from pendulum_kit.stock import Spool, StockUnavailable

SPOOLS = {"base": 1, "pillar": 1, "axle": 1, "arm": 2, "weight": 2}


class FakeStock:
    def __init__(self, grams=1000.0, alive=True):
        self.alive, self.used = alive, {}
        self._spools = {i: Spool(i, f"PLA {i}", "PLA", "ff0000", 1.24, grams) for i in (1, 2)}

    def spools(self):
        if not self.alive:
            raise StockUnavailable("down")
        return self._spools

    def use(self, sid, grams):
        self.used[sid] = self.used.get(sid, 0) + grams
        self._spools[sid].remaining_g -= grams
        return self._spools[sid]


PRINTER = {"x_mm": 256, "y_mm": 256, "z_mm": 256}


def run(tmp_path, stock, printer=PRINTER, **kw):
    order = Order(order_id="t", customer="test", **{"target_period_s": 0.7, "spool_ids": SPOOLS, **kw})
    return process_order(order, stock, out_root=tmp_path, make_cad=False, run_sim=False, printer=printer)


def test_produced(tmp_path):
    s = FakeStock()
    r = run(tmp_path, s)
    assert r["status"] == "produced" and abs(r["error_to_target_ms"]) < 5
    assert s.used[1] > 0 and s.used[2] > 0
    assert (tmp_path / "t" / "params.json").exists()
    assert json.loads((tmp_path / "t" / "report.json").read_text())["frequency_hz"] == pytest.approx(1 / 0.7, rel=1e-2)


@pytest.mark.parametrize("kw, status", [
    (dict(target_period_s=1.5), "rejected"),
    (dict(printer={"x_mm": 256, "y_mm": 256, "z_mm": 150}, target_period_s=0.8), "rejected"),
    (dict(spool_ids={"base": 1}), "rejected"),
])
def test_rejected(tmp_path, kw, status):
    assert run(tmp_path, FakeStock(), **kw)["status"] == status


def test_stock_down_postponed(tmp_path):
    assert run(tmp_path, FakeStock(alive=False))["status"] == "postponed"


def test_too_little_filament_postponed_and_nothing_used(tmp_path):
    s = FakeStock(grams=5)
    assert run(tmp_path, s)["status"] == "postponed" and s.used == {}


def test_order_by_length(tmp_path):
    from pendulum_kit.params import KitInputs
    from pendulum_kit.physics import period
    r = run(tmp_path, FakeStock(), target_period_s=None, pendulum_length_mm=150)
    assert r["status"] == "produced" and r["pendelumLenght_mm"] == 150
    assert r["period_formula_s"] == pytest.approx(period(KitInputs(pendelumLenght=150)).period_s, abs=1e-5)


@pytest.mark.parametrize("kw", [dict(target_period_s=None, pendulum_length_mm=300),   # too long
                                dict(target_period_s=None, pendulum_length_mm=10),    # too short
                                dict(target_period_s=None),                           # neither
                                dict(pendulum_length_mm=120)])                        # both
def test_bad_length_orders_rejected(tmp_path, kw):
    assert run(tmp_path, FakeStock(), **kw)["status"] == "rejected"


def test_check_order_keeps_orders_inside_the_printer():
    from pendulum_kit.orders import check_order
    small = {"x_mm": 180, "y_mm": 180, "z_mm": 150}
    assert check_order(Order("a", "b", target_period_s=0.7), PRINTER) == []
    assert check_order(Order("a", "b", target_period_s=0.8), small)            # too tall for 150 mm
    assert check_order(Order("a", "b", pendulum_length_mm=230), PRINTER)       # too long
    assert check_order(Order("a", "b", target_period_s=0.6, weightDiameter=230), PRINTER)   # base too wide
    assert check_order(Order("a", "b"), PRINTER)                               # neither period nor length


def test_old_saved_orders_still_load():
    o = Order.from_dict({"order_id": "x", "customer": "y", "target_period_s": 0.7, "max_height_mm": 200})
    assert o.target_period_s == 0.7
