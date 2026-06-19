"""Repair china_cities_zh.json: the translator emitted unescaped straight double-quotes inside
Chinese string values (e.g. 中国"磁都"). Convert any double-quote that is NOT adjacent to a JSON
structural delimiter (its nearest non-space neighbour on a side is one of : { [ , } ]) into a
typographic quote, leaving structural quotes intact. Then validate."""
import json
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "data" / "china_cities_zh.json"
s = p.read_text(encoding="utf-8")
n = len(s)


def nonspace_left(i):
    j = i - 1
    while j >= 0 and s[j] in " \t\r\n":
        j -= 1
    return s[j] if j >= 0 else ""


def nonspace_right(i):
    j = i + 1
    while j < n and s[j] in " \t\r\n":
        j += 1
    return s[j] if j < n else ""


res, fixes = [], 0
for i, ch in enumerate(s):
    if ch == '"':
        if i > 0 and s[i - 1] == "\\":      # already escaped
            res.append(ch)
            continue
        l, r = nonspace_left(i), nonspace_right(i)
        if (l in ":{[,") or (r in ",}]:"):  # structural quote
            res.append('"')
        else:                                # content quote inside a value
            res.append("”")
            fixes += 1
    else:
        res.append(ch)

fixed = "".join(res)
d = json.loads(fixed)   # raises if still broken
p.write_text(fixed, encoding="utf-8")
print(f"repaired {fixes} content quotes -> valid JSON, {len(d)} cities")
