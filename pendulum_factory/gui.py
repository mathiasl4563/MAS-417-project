"""
Basic Flask GUI for the pendulum-kit factory.

AI-ASSISTED: generated with Claude (Anthropic). Mention it in "Use of AI".

Run from the project root:
    flask --app pendulum_factory.gui run
"""

from flask import Flask, render_template, request

app = Flask(__name__)

# Form name -> text shown to the customer
PARTS = {
    "base": "Base",
    "stand_sides": "Stand sides",
    "arm": "Arm",
    "weight": "Weight",
    "axle": "Axle",
}

# Placeholder list. Later: fetch these from Spoolman (GET /api/v1/filament).
FILAMENTS = ["PLA Black", "PLA Red", "PETG Blue"]

# Limits. Adjust to your makerspace printers and your design.
MIN_PERIOD_S = 0.3
MAX_PERIOD_S = 2.0
MAX_HEIGHT_MM = 250


def read_number(form: dict, key: str, label: str, errors: list) -> float | None:
    """Read one positive number from the form. Adds a message to errors if it fails."""
    try:
        value = float(form.get(key, ""))
    except ValueError:
        errors.append(f"{label} must be a number.")
        return None
    if value <= 0:
        errors.append(f"{label} must be positive.")
        return None
    return value


def validate_order(form: dict) -> list[str]:
    """Check an order. Returns a list of reasons it failed (empty list = OK)."""
    errors = []

    if not form.get("customer", "").strip():
        errors.append("Name is required.")

    period = read_number(form, "period_s", "Swing period", errors)
    height = read_number(form, "max_height_mm", "Max height", errors)
    read_number(form, "axle_diameter_mm", "Axle diameter", errors)

    if period is not None and not MIN_PERIOD_S <= period <= MAX_PERIOD_S:
        errors.append(f"Swing period must be between {MIN_PERIOD_S} and {MAX_PERIOD_S} s.")
    if height is not None and height > MAX_HEIGHT_MM:
        errors.append(f"Max height cannot be more than {MAX_HEIGHT_MM} mm (printer build volume).")

    for key, label in PARTS.items():
        if form.get(f"filament_{key}") not in FILAMENTS:
            errors.append(f"Select a filament for the {label.lower()}.")

    return errors


@app.route("/", methods=["GET", "POST"])
def index():
    form = {}
    errors = []
    order = None

    if request.method == "POST":
        form = request.form.to_dict()
        errors = validate_order(form)
        if not errors:
            order = form          # accepted. Later: process_order(order)

    return render_template(
        "index.html", parts=PARTS, filaments=FILAMENTS,
        form=form, errors=errors, order=order,
    )


if __name__ == "__main__":
    app.run(debug=True)