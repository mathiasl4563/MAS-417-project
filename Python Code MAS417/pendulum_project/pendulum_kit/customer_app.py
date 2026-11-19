# Customer site: see the material in stock, place an order, follow its status. Cannot start production.
# Run:  python -m pendulum_kit.customer_app      -> http://localhost:5000
#   /                 order form
#   /orders/<id>      status of one order
#   POST /api/orders, GET /api/orders/<id>   the same as JSON
# Use of AI: generated with AI assistance (Claude), checked by the group.

import math

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from . import order_queue
from .orders import Order, check_order, order_limits
from .params import PRINT_PARTS
from .stock import StockClient, StockError

app = Flask(__name__)
stock = StockClient()
# Limits shown to the customer are rounded INWARDS, so every value shown can really be ordered
app.jinja_env.filters["down"] = lambda x, d=0: f"{math.floor(x * 10 ** d) / 10 ** d:.{d}f}"
app.jinja_env.filters["up"] = lambda x, d=0: f"{math.ceil(x * 10 ** d) / 10 ** d:.{d}f}"


# The customer chooses by period or by length; only the chosen one is sent on
def order_from_form(f):
    num = lambda key, default: float(f.get(key) or default)
    by_length = f.get("choose_by") == "length"
    return Order(order_id=order_queue.new_id(), customer=f.get("customer") or "anonymous",
                 target_period_s=None if by_length else num("target_period_s", 0.7),
                 pendulum_length_mm=num("pendulum_length_mm", 100) if by_length else None,
                 weightDiameter=num("weightDiameter", 30), infill=num("infill_pct", 15) / 100,
                 wall_loops=int(num("wall_loops", 2)),
                 spool_ids={p: int(f[f"spool_{p}"]) for p in PRINT_PARTS})


@app.get("/")
def order_form(error=None, form=None):
    try:
        spools = list(stock.spools().values())
    except StockError:
        spools, error = [], "The material stock is not available right now. Please try again later."
    return render_template("customer/order.html", spools=spools, parts=PRINT_PARTS, error=error,
                           lim=order_limits(), form=form or {})


@app.post("/")
def place_order():
    try:
        order = order_from_form(request.form)
    except (KeyError, ValueError) as e:
        return order_form(error=f"Invalid input: {e}", form=request.form), 400
    problems = check_order(order)
    if problems:
        return order_form(error=" ".join(problems), form=request.form), 400
    order_queue.save(order)
    return redirect(url_for("status", order_id=order.order_id))


@app.get("/orders/<order_id>")
def status(order_id):
    rec = order_queue.get(order_id)
    if rec is None:
        abort(404)
    return render_template("customer/status.html", rec=rec, rep=order_queue.report(order_id))


@app.post("/api/orders")
def api_place_order():
    d = request.get_json(force=True)
    d["order_id"] = order_queue.new_id()
    try:
        order = Order(**d)
    except TypeError as e:
        return jsonify(error=str(e)), 400
    problems = check_order(order)
    if problems:
        return jsonify(error=" ".join(problems)), 400
    order_queue.save(order)
    return jsonify(order_id=order.order_id, status="waiting"), 201


@app.get("/api/orders/<order_id>")
def api_status(order_id):
    rec = order_queue.get(order_id)
    if rec is None:
        return jsonify(error="not found"), 404
    rep = order_queue.report(order_id) or {}
    return jsonify(order_id=order_id, status=rec["status"], reason=rep.get("reason"),
                   period_s=rep.get("period_simulated_s") or rep.get("period_formula_s"),
                   pendulum_length_mm=rep.get("pendelumLenght_mm"),
                   frequency_hz=rep.get("frequency_hz"))


if __name__ == "__main__":
    app.run(port=5000, debug=True)
