r"""Validate the layered universe: counts by layer/sublayer/region + duplicate check.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\universe_stats.py
"""
from collections import Counter

from emi.config import iter_universe

rows = list(iter_universe())
print(f"TOTAL companies: {len(rows)}\n")

by_layer = Counter()
by_region = Counter()
seen = {}
dupes = []
for r in rows:
    by_layer[f"{r['layer']} {r['layer_name']}"] += 1
    by_region[r["region"]] += 1
    tk = r["ticker"]
    if tk in seen:
        dupes.append((tk, seen[tk], r["name"]))
    else:
        seen[tk] = r["name"]

print("By layer:")
for k in sorted(by_layer):
    print(f"  {k:34s} {by_layer[k]:3d}")

print("\nBy region:")
for k, v in by_region.most_common():
    print(f"  {k:4s} {v:3d}")

print(f"\nUnique tickers: {len(seen)}")
if dupes:
    print(f"DUPLICATE tickers ({len(dupes)}):")
    for tk, a, b in dupes:
        print(f"  {tk}: {a}  <->  {b}")
else:
    print("No duplicate tickers.")
