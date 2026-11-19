# Operator, without the GUI: process every order in a JSON file.
# Run:  python scripts/run_orders.py data/example_orders.json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pendulum_kit.orders import load_orders, process_order  # noqa: E402
from pendulum_kit.stock import StockClient  # noqa: E402

stock = StockClient()
for order in load_orders(sys.argv[1]):
    r = process_order(order, stock)
    print(f"{order.order_id:20s} {r['status']:9s} {r['reason']}")
