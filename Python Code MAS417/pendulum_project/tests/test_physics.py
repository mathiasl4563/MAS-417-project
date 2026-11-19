import math
from dataclasses import replace

import pytest

from pendulum_kit.params import KitInputs
from pendulum_kit.physics import bisection, part_list, period, period_range, printed_mass_g, solve_length


def test_full_infill_is_solid():
    k = KitInputs(infill=1.0)
    assert printed_mass_g(1000, 600, 1.24, k) == pytest.approx(1.24)


def test_heavy_weight_matches_hand_calculation():
    # only the weight has mass -> T = 2 pi sqrt((L^2 + (3R^2 + h^2)/12) / (g L))
    k = KitInputs(infill=1.0)
    for part in k.filaments:
        k.filaments[part].density_g_cm3 = 1e-9
    k.filaments["weight"].density_g_cm3 = 1.24
    L, R, h = 0.100, 0.015, 0.030
    t_hand = 2 * math.pi * math.sqrt((L ** 2 + (3 * R ** 2 + h ** 2) / 12) / (9.81 * L))
    # the arm slot makes the weight a little lighter in the middle -> small difference
    assert period(k, 0).period_s == pytest.approx(t_hand, rel=2e-3)


def test_period_grows_with_length():
    ts = [period(KitInputs(pendelumLenght=L)).period_s for L in range(25, 220, 15)]
    assert ts == sorted(ts)


def test_frequency():
    p = period(KitInputs())
    assert p.frequency_hz == pytest.approx(1 / p.period_s)


def test_bisection():
    assert bisection(lambda x: x * x - 2, 0, 2, tol=1e-10) == pytest.approx(math.sqrt(2))


@pytest.mark.parametrize("target", [0.40, 0.55, 0.70, 0.85])
def test_solver_hits_target(target):
    s = solve_length(KitInputs(target_period_s=target))
    assert s.feasible and abs(s.error_ms) < 0.1


def test_solver_rejects_unreachable():
    assert not solve_length(KitInputs(target_period_s=1.5)).feasible


def test_lower_printer_gives_shorter_max_period():
    assert period_range(KitInputs(zPrint=150))[1] < period_range(KitInputs())[1]


def test_masses_positive():
    assert all(p.mass_g > 0 for p in part_list(KitInputs()))
