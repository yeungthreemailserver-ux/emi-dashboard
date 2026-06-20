r"""Run the Streamlit app through its own test runtime and assert every view renders.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\apptest.py
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")

at = AppTest.from_file(APP, default_timeout=90)
at.run()
assert not at.exception, f"initial render: {at.exception}"

for label in ["Competitive scorecard", "End-market demand", "Company drill-down", "Cycle pulse"]:
    at.radio[0].set_value(label).run()
    assert not at.exception, f"{label}: {at.exception}"
    print(f"  OK  {label}")

print("APPTEST OK — all 4 views render without exception")
