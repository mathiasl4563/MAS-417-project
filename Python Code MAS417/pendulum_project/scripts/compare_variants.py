# Compares design variants: formula vs MuJoCo, run in parallel processes.
# Run:  python scripts/compare_variants.py      -> output/variants.csv
# Use of AI: generated with AI assistance (Claude), checked by the group.
import csv
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pendulum_kit.params import KitInputs  # noqa: E402
from pendulum_kit.physics import period  # noqa: E402
from pendulum_kit.simulation import simulate  # noqa: E402

VARIANTS = {
    "A short, 15 %": dict(pendelumLenght=60),
    "B long, 15 %": dict(pendelumLenght=180),
    "C long, 100 %": dict(pendelumLenght=180, infill=1.0),
    "D long, big weight": dict(pendelumLenght=180, weightDiameter=45),
    "E long, 10 deg": dict(pendelumLenght=180, amplitude_deg=10),
}


def row(item):
    name, changes = item
    k = replace(KitInputs(), **changes)
    f, sim = period(k), simulate(k)
    return {"variant": name, **changes, "mass_g": round(f.mass_g, 2), "T_formula_s": round(f.period_s, 5),
            "T_mujoco_s": round(sim.period_s, 5), "f_hz": round(sim.frequency_hz, 4),
            "diff_ms": round((sim.period_s - f.period_s) * 1000, 3)}


if __name__ == "__main__":
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(row, VARIANTS.items()))
    Path("output").mkdir(exist_ok=True)
    keys = sorted({key for r in rows for key in r}, key=lambda x: list(rows[0]).index(x) if x in rows[0] else 99)
    with open("output/variants.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['variant']:20s} m={r['mass_g']:6.2f} g  formula {r['T_formula_s']:.4f} s  "
              f"MuJoCo {r['T_mujoco_s']:.4f} s  ({r['diff_ms']:+.2f} ms)")
    print("Saved output/variants.csv")
