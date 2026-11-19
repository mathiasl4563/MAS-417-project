# Pendulum kit – MAS417

## Needs

Python 3.11 or newer, and Docker Desktop.

## Install

```bash
python -m venv .venv
.venv\\\\Scripts\\\\Activate.ps1          # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

Start Docker Desktop, then:

```bash
docker compose up -d                # starts Spoolman
python scripts/seed\\\_stock.py        # first time only: adds the filaments
python scripts/start\\\_sites.py       # starts the websites
```

* Customer: http://localhost:5000
* Operator: http://localhost:5001

Files for each order are saved in `output/`. Run the tests with `python -m pytest`.

