# Both sites with a fake stock and temporary folders (no Docker, CadQuery or MuJoCo needed)
# Use of AI: generated with AI assistance (Claude), checked by the group.
import pytest

import pendulum_kit.customer_app as customer
import pendulum_kit.operator_app as operator
import pendulum_kit.order_queue as order_queue
import pendulum_kit.orders as orders
from tests.test_orders import FakeStock

PARTS = ["base", "pillar", "axle", "arm", "weight"]


@pytest.fixture
def sites(tmp_path, monkeypatch):
    stock = FakeStock()
    stock.is_alive = lambda: True
    monkeypatch.setattr(order_queue, "QUEUE", tmp_path / "queue")
    monkeypatch.setattr(order_queue, "OUTPUT", tmp_path / "out")
    monkeypatch.setattr(operator, "OUTPUT", tmp_path / "out")
    monkeypatch.setattr(customer, "stock", stock)
    monkeypatch.setattr(operator, "stock", stock)
    real = orders.process_order
    monkeypatch.setattr(operator, "process_order",
                        lambda o, s: real(o, s, out_root=tmp_path / "out", make_cad=False, run_sim=False))
    return customer.app.test_client(), operator.app.test_client()


def place(c, period="0.7"):
    form = {"customer": "Ada", "target_period_s": period, **{f"spool_{p}": "1" for p in PARTS}}
    r = c.post("/", data=form)
    assert r.status_code == 302
    return r.headers["Location"].split("/")[-1]


def test_customer_form_has_no_removed_options(sites):
    page = sites[0].get("/").data.decode()
    assert "Place order" in page
    for gone in ("axleDiameter", "max_material_g", "assembled", "max_height_mm", "Max kit height",
                 "Production", "Start production"):
        assert gone not in page


def test_customer_cannot_start_production(sites):
    oid = place(sites[0])
    assert sites[0].post(f"/start/{oid}").status_code in (404, 405)


def test_order_flow_across_both_sites(sites):
    c, op = sites
    oid = place(c)
    assert "waiting" in c.get(f"/orders/{oid}").data.decode()
    assert oid in op.get("/").data.decode()
    assert op.post(f"/start/{oid}").status_code == 302
    assert "produced" in c.get(f"/orders/{oid}").data.decode()
    assert c.get(f"/api/orders/{oid}").json["status"] == "produced"
    assert "Pendulum length" in op.get(f"/orders/{oid}").data.decode()


def test_order_outside_printer_is_refused_on_the_form(sites):
    c, op = sites
    form = {"customer": "Ada", "target_period_s": "1.5", **{f"spool_{p}": "1" for p in PARTS}}
    r = c.post("/", data=form)
    assert r.status_code == 400 and "fit the printer" in r.data.decode()
    assert 'value="1.5"' in r.data.decode()          # the form keeps what was typed
    assert "No orders yet" in op.get("/").data.decode()
    r = c.post("/api/orders", json={"customer": "Bob", "pendulum_length_mm": 300, "spool_ids": {p: 1 for p in PARTS}})
    assert r.status_code == 400


def test_printer_section_on_both_sites(sites):
    assert "256 × 256 × 256 mm" in sites[0].get("/").data.decode()
    assert "256 × 256 × 256 mm" in sites[1].get("/").data.decode()


def test_api_order(sites):
    c, op = sites
    r = c.post("/api/orders", json={"customer": "Bob", "target_period_s": 0.6, "spool_ids": {p: 1 for p in PARTS}})
    assert r.status_code == 201
    op.post(f"/start/{r.json['order_id']}")
    assert c.get(f"/api/orders/{r.json['order_id']}").json["status"] == "produced"


def test_stock_error_shows_message_not_crash(sites, monkeypatch):
    from pendulum_kit.stock import StockError

    def broken():
        raise StockError("GET /spool -> HTTP 500")
    monkeypatch.setattr(customer.stock, "spools", broken)
    r = sites[0].get("/")
    assert r.status_code == 200 and "not available" in r.data.decode()


def test_order_by_length_on_the_form(sites):
    c, op = sites
    page = c.get("/").data.decode()
    assert "Pendulum length" in page and "pendulum_length_mm" in page
    form = {"customer": "Ada", "choose_by": "length", "pendulum_length_mm": "140",
            **{f"spool_{p}": "1" for p in PARTS}}
    oid = c.post("/", data=form).headers["Location"].split("/")[-1]
    op.post(f"/start/{oid}")
    status = c.get(f"/api/orders/{oid}").json
    assert status["status"] == "produced" and status["pendulum_length_mm"] == 140
    assert "140.0 mm" in op.get("/").data.decode()
    assert "Length you asked for" in c.get(f"/orders/{oid}").data.decode()



def test_operator_starts_only_the_chosen_order(sites):
    c, op = sites
    first, second = place(c), place(c, "0.6")
    page = op.get("/").data.decode()
    assert f"/start/{first}" in page and f"/start/{second}" in page
    op.post(f"/start/{second}")
    assert c.get(f"/api/orders/{first}").json["status"] == "waiting"
    assert c.get(f"/api/orders/{second}").json["status"] == "produced"
    page = op.get("/").data.decode()
    assert f"/start/{first}" in page and f"/start/{second}" not in page
    assert op.post(f"/start/{second}").status_code == 404      # already produced
