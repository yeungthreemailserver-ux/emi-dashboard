r"""Data validation: flag implausible revenue values / growth + calendar-quarter gaps.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\validate_data.py
"""
import json

from emi.config import ROOT


def qi(q):
    return int(q[:4]) * 4 + (int(q[5]) - 1)


d = json.load(open(ROOT / "web" / "data.json", encoding="utf-8"))
issues = []
for c in d["companies"]:
    q = c["q"]
    cal, rev = q["calq"], q["revenue"]["v"]
    # non-positive revenue
    for i, v in enumerate(rev):
        if v is not None and v <= 0:
            issues.append((c["ticker"], "rev<=0", cal[i], round((v or 0) / 1e9, 2)))
    # implausible growth
    for i in range(len(cal)):
        yy, qq = q["revenue"]["yoy"][i], q["revenue"]["qoq"][i]
        if yy is not None and (yy > 2.5 or yy < -0.9):
            issues.append((c["ticker"], "YoY", cal[i], f"{yy*100:.0f}%"))
        if qq is not None and (qq > 0.8 or qq < -0.5):
            issues.append((c["ticker"], "QoQ", cal[i], f"{qq*100:.0f}%"))
    # calendar gaps within the company's own span
    ints = [qi(x) for x in cal]
    for a, b in zip(ints, ints[1:]):
        if b - a != 1:
            issues.append((c["ticker"], "GAP", f"{cal[ints.index(a)]}→{cal[ints.index(b)]}", b - a))

print(f"{len(issues)} issues\n")
for x in issues[:80]:
    print(x)
