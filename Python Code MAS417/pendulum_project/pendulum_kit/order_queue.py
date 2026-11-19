# The order queue shared by the two sites: one JSON file per order in data/orders/.
# The customer site adds orders, the operator site processes them.
# Use of AI: generated with AI assistance (Claude), checked by the group.

import json
import uuid
from dataclasses import asdict
from pathlib import Path

from .orders import OUTPUT, Order

QUEUE = Path(__file__).resolve().parent.parent / "data" / "orders"


def new_id():
    return f"o{uuid.uuid4().hex[:6]}"


def save(order, status="waiting"):
    QUEUE.mkdir(parents=True, exist_ok=True)
    (QUEUE / f"{order.order_id}.json").write_text(json.dumps({"status": status, "order": asdict(order)}, indent=2))


def get(order_id):
    f = QUEUE / f"{order_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def all_orders():
    recs = [json.loads(f.read_text()) for f in sorted(QUEUE.glob("*.json"), key=lambda f: f.stat().st_mtime)]
    return [r for r in recs if isinstance(r, dict) and "status" in r]


def waiting():
    return [Order.from_dict(r["order"]) for r in all_orders() if r["status"] in ("waiting", "postponed")]


def report(order_id):
    f = OUTPUT / order_id / "report.json"
    return json.loads(f.read_text()) if f.exists() else None
