# Material stock: the only file that talks to Spoolman (REST).
# Spoolman API docs: http://localhost:7912/api/v1/docs (Swagger) or https://donkie.github.io/Spoolman/
# Calls: GET /health, GET+POST /vendor, /filament, /spool, PUT /spool/{id}/use {"use_weight": grams}
# Use of AI: generated with AI assistance (Claude); field names checked by the group against Swagger.

import os
from dataclasses import dataclass

import requests

URL = os.environ.get("SPOOLMAN_URL", "http://localhost:7912")


class StockError(RuntimeError):            # Spoolman answered with an error
    pass


class StockUnavailable(StockError):        # Spoolman did not answer at all
    pass


@dataclass
class Spool:
    spool_id: int
    name: str
    material: str
    color_hex: str
    density_g_cm3: float
    remaining_g: float

    @classmethod
    def from_api(cls, s):
        f = s.get("filament", {})
        return cls(s["id"], f.get("name") or "?", f.get("material") or "?", f.get("color_hex") or "888888",
                   float(f.get("density") or 1.24), float(s.get("remaining_weight") or 0))


class StockClient:
    def __init__(self, url=URL, timeout_s=3.0):
        self.api = url.rstrip("/") + "/api/v1"
        self.timeout = timeout_s

    def _call(self, method, path, **kw):
        try:
            r = requests.request(method, self.api + path, timeout=self.timeout, **kw)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise StockUnavailable(f"Spoolman not reachable at {self.api}: {e}") from e
        if r.status_code >= 400:
            raise StockError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else None

    def is_alive(self):
        try:
            self._call("GET", "/health")
            return True
        except StockError:
            return False

    def spools(self):
        return {s["id"]: Spool.from_api(s) for s in self._call("GET", "/spool")}

    def use(self, spool_id, grams):
        return Spool.from_api(self._call("PUT", f"/spool/{spool_id}/use", json={"use_weight": round(grams, 2)}))

    # Operator: register makerspace filaments (scripts/seed_stock.py)
    def filament_names(self):
        return {f["name"] for f in self._call("GET", "/filament")}

    def vendor_id(self, name):
        for v in self._call("GET", "/vendor"):
            if v["name"] == name:
                return v["id"]
        return self._call("POST", "/vendor", json={"name": name})["id"]

    def add_filament(self, vendor_id, name, material, density, diameter=1.75, weight=1000,
                     spool_weight=None, color_hex=None):
        body = {"name": name, "vendor_id": vendor_id, "material": material, "density": density,
                "diameter": diameter, "weight": weight}
        if spool_weight is not None:
            body["spool_weight"] = spool_weight
        if color_hex:
            body["color_hex"] = color_hex.lstrip("#")
        return self._call("POST", "/filament", json=body)["id"]

    def add_spool(self, filament_id, grams, location="UiA makerspace"):
        body = {"filament_id": filament_id, "initial_weight": grams, "remaining_weight": grams, "location": location}
        return self._call("POST", "/spool", json=body)["id"]


# Grams needed per spool vs grams left (with safety margin); returns problems
def check_stock(needs_g, spools, margin=1.10):
    problems = []
    for sid, grams in needs_g.items():
        s = spools.get(sid)
        if s is None:
            problems.append(f"spool {sid} does not exist")
        elif s.remaining_g < grams * margin:
            problems.append(f"spool {sid} ({s.name}) has {s.remaining_g:.1f} g, needs {grams * margin:.1f} g "
                            f"incl. {round((margin - 1) * 100)} % margin")
    return problems
