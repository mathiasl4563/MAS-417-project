# Operator: register the makerspace filaments in data/stock.json in Spoolman (one spool each).
# Run:  python scripts/seed_stock.py      (skips filaments that already exist)
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pendulum_kit.stock import StockClient, StockUnavailable  # noqa: E402

stock = StockClient()
try:
    existing = stock.filament_names()
except StockUnavailable as e:
    sys.exit(f"Spoolman is not running ({e}). Start it with: docker compose up -d")
for f in json.loads(Path("data/stock.json").read_text())["filaments"]:
    if f["name"] in existing:
        print("skip ", f["name"])
        continue
    fid = stock.add_filament(stock.vendor_id(f["vendor"]), f["name"], f["material"], f["density"],
                             f["diameter"], f["net_weight_g"], f.get("spool_weight_g"), f.get("color_hex"))
    print(f"added {f['name']}: filament {fid}, spool {stock.add_spool(fid, f['net_weight_g'])}")
