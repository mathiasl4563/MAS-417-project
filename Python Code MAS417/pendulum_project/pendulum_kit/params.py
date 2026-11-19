# Single source of truth: every input, derived value and check for one kit.
# CAD (cad.py), calculations (physics.py) and simulation (simulation.py) all read KitInputs.
# One kit = one params.json in output/<order_id>/.
# Use of AI: structure generated with AI assistance (Claude) from the group's CAD script.

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace

PRINT_PARTS = ("base", "pillar", "axle", "arm", "weight")  # one filament (spool) per part
PRINTER_FILE = Path(__file__).resolve().parent.parent / "data" / "printer.json"


# Print bed size [mm] from data/printer.json (256 x 256 x 256 if the file is missing)
def load_printer(path=None):
    f = Path(path or PRINTER_FILE)
    d = json.loads(f.read_text()) if f.exists() else {}
    return {"x_mm": float(d.get("x_mm", 256)), "y_mm": float(d.get("y_mm", 256)), "z_mm": float(d.get("z_mm", 256))}


@dataclass
class Filament:
    spool_id: int | None = None
    name: str = "PLA (default)"
    material: str = "PLA"
    density_g_cm3: float = 1.24
    color_hex: str = "888888"


@dataclass
class KitInputs:
    # Order
    order_id: str = "test"
    target_period_s: float | None = None
    assembled: bool = True            # print-in-place kit in one 3MF (False: one 3MF per part, not used by orders)
    # Input values (solver sets pendelumLenght from target_period_s)
    pendelumLenght: float = 100
    weightDiameter: float = 30
    weightHeight: float = 30
    # Print area (print bed), set from data/printer.json for orders
    xPrint: float = 256
    yPrint: float = 256
    zPrint: float = 256
    # Tolerances
    squareTolerance: float = 0.2
    circleTolerance: float = 0.5
    axleTolerance: float = 0.5
    weightTolerance: float = 5
    WeightDistanceTolerance: float = 5
    # Static values
    squareHoleHeight: float = 20
    squareHoleWidth: float = 5
    baseThickness: float = 5
    axleDistanceFromTop: float = 5
    axleDiameter: float = 5
    axleCuttof: float = 5
    pendelumArmBaseThickness: float = 10
    pendelumArmArmThickness: float = 5
    # Print settings
    infill: float = 0.15
    wall_loops: int = 2
    line_width_mm: float = 0.42
    top_bottom_layers: int = 4
    layer_height_mm: float = 0.2
    # Simulation
    amplitude_deg: float = 45.0
    damping: float = 0.0              # keep tiny, e.g. 0.000005
    # Filament per part
    filaments: dict = field(default_factory=lambda: {p: Filament() for p in PRINT_PARTS})

    def save(self, path):
        d = asdict(self)
        d["derived"] = vars(derive(self))
        Path(path).write_text(json.dumps(d, indent=2))

    @classmethod
    def load(cls, path):
        d = json.loads(Path(path).read_text())
        d.pop("derived", None)
        d["filaments"] = {p: Filament(**f) for p, f in d.get("filaments", {}).items()}
        return cls(**d)


class CadValidationError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


# Derived values, same formulas as the group's CAD script
def derive(k):
    L, h, D = k.pendelumLenght, k.weightHeight, k.weightDiameter
    shd = max(D + k.weightTolerance * 2 + k.squareHoleWidth, 50)
    wdb = math.sqrt((L + h / 2) ** 2 + (D / 2) ** 2) + k.WeightDistanceTolerance - L - h / 2
    pillar = k.baseThickness + L + wdb + k.axleDistanceFromTop + h / 2
    return SimpleNamespace(
        squareHoleDistance=shd,
        baseDiameter=shd + 20,
        weightDistanseToBase=wdb,
        pillarHeight=pillar,
        axleZ=pillar - k.axleDistanceFromTop,
        hubLength=shd - k.squareHoleWidth - k.axleTolerance * 2,
        axleLength=2 * ((shd + 20) / 2 - k.axleCuttof),
        armLength=L + h / 2 - k.pendelumArmBaseThickness / 2,
        weightBottomZ=wdb + k.baseThickness,
    )


# All checks; returns a list of problems (empty = valid)
def validate(k):
    g = derive(k)
    p = []
    for name in ("pendelumLenght", "weightDiameter", "weightHeight", "axleDiameter", "baseThickness"):
        if getattr(k, name) <= 0:
            p.append(f"Error: {name} must be > 0")
    if k.weightDiameter < 15:
        p.append("Error: weightDiameter is too small, minimum 15mm")
    if k.weightDiameter > k.xPrint - 12.5 * 2 - k.weightTolerance * 2:
        p.append(f"Error: weightDiameter is too large, maximum {k.xPrint - 12.5 * 2 - k.weightTolerance * 2}mm")
    if g.pillarHeight > k.zPrint:
        p.append("Error: pillars are outside the base")
    if k.pendelumLenght - k.weightHeight / 2 < k.pendelumArmBaseThickness / 2 + 1:
        p.append("Error: weight hits the hub, pendelumLenght too short")
    if k.axleDiameter + 3 > k.pendelumArmBaseThickness:
        p.append("Error: axleDiameter too large for the 10mm hub (needs 1.5mm wall)")
    if g.baseDiameter > min(k.xPrint, k.yPrint):
        p.append("Error: base does not fit the print area")
    if not 0 <= k.infill <= 1:
        p.append("Error: infill must be 0-100 %")
    if k.wall_loops < 1:
        p.append("Error: wall_loops must be at least 1")
    return p


def validate_or_raise(k):
    problems = validate(k)
    if problems:
        raise CadValidationError(problems)
