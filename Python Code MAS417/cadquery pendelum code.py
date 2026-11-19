import cadquery as cq
import math


class CadValidationError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems  # list of all problems found, not just the first


problems = []  # every failed check is collected here

Assembeled = 1 # 1=yes 0=no

# Print area 
xPrint = 256
yPrint = 256
zPrint = 256

# Tolerances
squareTolerance = 0.2
circleTolerance = 0.5
axleTolerance = 0.5
weightTolerance = 5
WeightDistanceTolerance = 5


# Innput values
pendelumLenght = 200 # minimum 20, maximum 256 - 5 - 5 - 20
weightDiameter = 100 # minimum 12, maximum 256-12.5*2-weightTolerance*2
weightHeight = 40 # static

# Static values
squareHoleHeight = 20 # static
squareHoleWidth = 5 # static
baseThickness = 5 # static
axleDistanceFromTop = 5 # static
axleDiameter = 5 # static
axleCuttof = 5 # static
pendelumArmBaseThickness = 10 # static
pendelumArmArmThickness = 5 # static


if weightDiameter < 15:
    problems.append("Error: weightDiameter is too small, minimum 15mm")

if weightDiameter > xPrint - 12.5*2 - weightTolerance*2:
    problems.append("Error: weightDiameter is too large, maximum " + str(xPrint - 12.5*2 - weightTolerance*2) + "mm")

# Driven values

squareHoleDistance = weightDiameter + weightTolerance*2 + squareHoleWidth

if squareHoleDistance < 50:
    squareHoleDistance = 50

baseDiameter = squareHoleDistance + 20 # squareHoleWidth + 20

weightDistanseToBase = math.sqrt((pendelumLenght + weightHeight/2)**2 + (weightDiameter/2)**2) + WeightDistanceTolerance - pendelumLenght - weightHeight/2

if (baseThickness + pendelumLenght + weightDistanseToBase + axleDistanceFromTop + weightHeight/2)> zPrint:
    problems.append("Error: pillars are outside the base")

# Stop here with ALL problems at once (instead of sys.exit on the first one)
if problems:
    raise CadValidationError(problems)

base = (
    cq.Workplane("XY")
    .circle(baseDiameter / 2)
    .extrude(baseThickness)
)

# One slot on the right side
slot = (
    cq.Workplane("XY")
    .center(squareHoleDistance / 2, 0)
    .rect(squareHoleWidth+squareTolerance, squareHoleHeight+squareTolerance)
    .extrude(baseThickness)
)

# Mirror the slot across the YZ plane (about the Y axis) and cut both
slots = slot.union(slot.mirror("YZ"))
base = base.cut(slots)

pillar = (
    cq.Workplane("XY")
    .center(squareHoleDistance / 2, 0)
    .rect(squareHoleWidth, squareHoleHeight)
    .extrude(baseThickness + pendelumLenght + weightDistanseToBase + axleDistanceFromTop + weightHeight/2)
)

# Mirror the pillar across the YZ plane (about the Y axis) and union both
pillars = pillar.union(pillar.mirror("YZ"))

axleHole = (
    cq.Workplane("YZ")
    .center(0, baseThickness + pendelumLenght + weightDistanseToBase + axleDistanceFromTop + weightHeight/2 - axleDistanceFromTop)
    .circle(axleDiameter / 2 + circleTolerance)
    .extrude(baseDiameter, both=True)
)

pillars = pillars.cut(axleHole)

axle = (
    cq.Workplane("YZ")    
    .center(0, baseThickness + pendelumLenght + weightDistanseToBase + axleDistanceFromTop + weightHeight/2 - axleDistanceFromTop)
    .circle(axleDiameter / 2)
    .extrude(baseDiameter/2 - axleCuttof, both=True)
)

pendelumArmBase = (
    cq.Workplane("YZ")    
        .center(0, baseThickness + pendelumLenght + weightDistanseToBase + axleDistanceFromTop + weightHeight/2 - axleDistanceFromTop)
        .rect(pendelumArmBaseThickness, pendelumArmBaseThickness)
        .extrude((squareHoleDistance - squareHoleWidth - axleTolerance*2)/2, both=True)
)
pendelumArmBase = pendelumArmBase.cut(axle)

pendelumArmArm = ( 
    cq.Workplane("XY")
        .workplane(offset=weightDistanseToBase + baseThickness)
        .center(0, 0)
        .rect(pendelumArmArmThickness, pendelumArmBaseThickness)
        .extrude(pendelumLenght + weightHeight/2 - pendelumArmBaseThickness/2)
)

weight = (
    cq.Workplane("XY")
        .workplane(offset=weightDistanseToBase + baseThickness)
        .center(0, 0)
        .circle(weightDiameter/2)
        .extrude(weightHeight)
)

weightCut = (
    cq.Workplane("XY")
        .workplane(offset=weightDistanseToBase + baseThickness)
        .center(0, 0)
        .rect(pendelumArmArmThickness + squareTolerance, pendelumArmBaseThickness + squareTolerance)
        .extrude(weightHeight)
)
weight = weight.cut(weightCut)


figure = base.union(pillars).union(axle).union(pendelumArmBase).union(pendelumArmArm).union(weight)

cq.exporters.export(figure, "test.3mf")
print("Wrote test.3mf")