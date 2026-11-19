# Use of AI: generated with AI assistance (Claude), checked by the group.
from dataclasses import replace

from pendulum_kit.params import KitInputs, derive, validate


def test_defaults_are_valid():
    assert validate(KitInputs()) == []


def test_axle_to_weight_centre_is_pendelumLenght():
    k = KitInputs(pendelumLenght=137)
    g = derive(k)
    assert abs(g.axleZ - (g.weightBottomZ + k.weightHeight / 2) - 137) < 1e-9


def test_params_json(tmp_path):
    import json
    k = KitInputs(order_id="x", pendelumLenght=123.4)
    k.filaments["arm"].density_g_cm3 = 1.27
    k.save(tmp_path / "p.json")
    d = json.loads((tmp_path / "p.json").read_text())
    assert d["pendelumLenght"] == 123.4 and d["filaments"]["arm"]["density_g_cm3"] == 1.27
    assert d["derived"]["axleZ"] == derive(k).axleZ


def has(k, word):
    return any(word in p for p in validate(k))


def test_checks():
    k = KitInputs()
    assert has(replace(k, weightDiameter=10), "too small")
    assert has(replace(k, pendelumLenght=240), "outside")
    assert has(replace(k, zPrint=150, pendelumLenght=150), "outside")
    assert has(replace(k, pendelumLenght=15), "hits the hub")
    assert has(replace(k, infill=1.5), "infill")
