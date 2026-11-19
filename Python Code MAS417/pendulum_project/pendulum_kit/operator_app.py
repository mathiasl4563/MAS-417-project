# Operator site: see all orders, start production, open results and download the 3MF files.
# Run:  python -m pendulum_kit.operator_app      -> http://localhost:5001
#   /                 all orders, each waiting order with its own "Start" button
#   /orders/<id>      full result of one order, with files
# Use of AI: generated with AI assistance (Claude), checked by the group.

from flask import Flask, abort, redirect, render_template, send_from_directory, url_for

from . import order_queue
from .orders import OUTPUT, process_order
from .params import load_printer
from .stock import StockClient

app = Flask(__name__)
stock = StockClient()


@app.get("/")
def production():
    return render_template("operator/production.html", orders=order_queue.all_orders()[::-1],
                           alive=stock.is_alive(), printer=load_printer())


# Produces the one order the operator picked (only waiting or postponed orders)
@app.post("/start/<order_id>")
def start_order(order_id):
    order = next((o for o in order_queue.waiting() if o.order_id == order_id), None)
    if order is None:
        abort(404)
    order_queue.save(order, process_order(order, stock)["status"])
    return redirect(url_for("order_details", order_id=order_id))


@app.get("/orders/<order_id>")
def order_details(order_id):
    rec = order_queue.get(order_id)
    if rec is None:
        abort(404)
    return render_template("operator/order.html", rec=rec, rep=order_queue.report(order_id))


@app.get("/files/<order_id>/<name>")
def files(order_id, name):
    return send_from_directory(OUTPUT / order_id, name, as_attachment=name.endswith(".3mf"))


if __name__ == "__main__":
    app.run(port=5001, debug=True)
