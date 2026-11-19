# Starts both sites at once. Ctrl+C stops both.
#   customer: http://localhost:5000      operator: http://localhost:5001
# Run:  python scripts/start_sites.py
# Use of AI: generated with AI assistance (Claude), checked by the group.
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sites = [subprocess.Popen([sys.executable, "-m", f"pendulum_kit.{name}"], cwd=root)
         for name in ("customer_app", "operator_app")]
print("Customer site: http://localhost:5000\nOperator site: http://localhost:5001\nCtrl+C stops both.")
try:
    for s in sites:
        s.wait()
except KeyboardInterrupt:
    for s in sites:
        s.terminate()
