# Compares CadQuery's exact volumes with the volumes physics.py uses for mass. Good table for the report.
# Run:  python scripts/cad_check.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pendulum_kit.cad import cad_volumes  # noqa: E402
from pendulum_kit.params import KitInputs  # noqa: E402
from pendulum_kit.physics import part_list  # noqa: E402

k = KitInputs()
calc = {}
for p in part_list(k):
    key = {"pillars": "pillar", "hub": "arm"}.get(p.name, p.name)
    calc[key] = calc.get(key, 0) + p.volume
for name, v in cad_volumes(k).items():
    print(f"{name:8s} CadQuery {v:10.0f} mm3   physics.py {calc[name]:10.0f} mm3   {100 * (calc[name] / v - 1):+.2f} %")
