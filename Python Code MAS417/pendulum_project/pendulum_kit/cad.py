# The group's CadQuery geometry, as functions that read KitInputs (no global values, no sys.exit).
# Run alone:  python -m pendulum_kit.cad      -> output/test/test_kit.3mf with default inputs
# Use of AI: AI (Claude) moved the group's CAD script into functions; the geometry is the group's own.

from pathlib import Path

import cadquery as cq

from .params import KitInputs, derive, validate_or_raise


def make_base(k, g):
    base = cq.Workplane("XY").circle(g.baseDiameter / 2).extrude(k.baseThickness)
    slot = (cq.Workplane("XY").center(g.squareHoleDistance / 2, 0)
            .rect(k.squareHoleWidth + k.squareTolerance, k.squareHoleHeight + k.squareTolerance)
            .extrude(k.baseThickness))
    return base.cut(slot.union(slot.mirror("YZ")))


def make_pillars(k, g):
    pillar = (cq.Workplane("XY").center(g.squareHoleDistance / 2, 0)
              .rect(k.squareHoleWidth, k.squareHoleHeight).extrude(g.pillarHeight))
    hole = (cq.Workplane("YZ").center(0, g.axleZ)
            .circle(k.axleDiameter / 2 + k.circleTolerance).extrude(g.baseDiameter, both=True))
    return pillar.union(pillar.mirror("YZ")).cut(hole)


def make_axle(k, g):
    return (cq.Workplane("YZ").center(0, g.axleZ).circle(k.axleDiameter / 2)
            .extrude(g.baseDiameter / 2 - k.axleCuttof, both=True))


def make_hub(k, g):
    a = k.pendelumArmBaseThickness
    hub = (cq.Workplane("YZ").center(0, g.axleZ).rect(a, a)
           .extrude((g.squareHoleDistance - k.squareHoleWidth - k.axleTolerance * 2) / 2, both=True))
    return hub.cut(make_axle(k, g))


def make_arm(k, g):
    return (cq.Workplane("XY").workplane(offset=g.weightBottomZ)
            .rect(k.pendelumArmArmThickness, k.pendelumArmBaseThickness).extrude(g.armLength))


def make_weight(k, g):
    weight = (cq.Workplane("XY").workplane(offset=g.weightBottomZ)
              .circle(k.weightDiameter / 2).extrude(k.weightHeight))
    cut = (cq.Workplane("XY").workplane(offset=g.weightBottomZ)
           .rect(k.pendelumArmArmThickness + k.squareTolerance, k.pendelumArmBaseThickness + k.squareTolerance)
           .extrude(k.weightHeight))
    return weight.cut(cut)


# Printed parts; the hub is printed with the arm (same filament)
def make_parts(k):
    validate_or_raise(k)
    g = derive(k)
    return {
        "base": make_base(k, g),
        "pillar": make_pillars(k, g),
        "axle": make_axle(k, g),
        "arm": make_hub(k, g).union(make_arm(k, g)),
        "weight": make_weight(k, g),
    }


def make_kit(k):
    parts = list(make_parts(k).values())
    kit = parts[0]
    for part in parts[1:]:
        kit = kit.union(part)
    return kit


# The whole kit as one print-in-place 3MF
def export_3mf(k, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{k.order_id}_kit.3mf"
    cq.exporters.export(make_kit(k), str(path))
    return [path]


if __name__ == "__main__":
    for f in export_3mf(KitInputs(), Path("output") / "test"):
        print("Wrote", f)
