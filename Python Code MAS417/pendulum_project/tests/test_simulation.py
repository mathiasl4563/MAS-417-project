# Runs only where MuJoCo is installed
# Use of AI: generated with AI assistance (Claude), checked by the group.
import pytest

mujoco = pytest.importorskip("mujoco")

from pendulum_kit.params import KitInputs  # noqa: E402
from pendulum_kit.physics import period  # noqa: E402
from pendulum_kit.simulation import simulate  # noqa: E402


@pytest.mark.parametrize("amp", [10, 45])
def test_mujoco_matches_formula(amp):
    k = KitInputs(amplitude_deg=amp)
    assert simulate(k, 6).period_s == pytest.approx(period(k).period_s, rel=3e-3)
