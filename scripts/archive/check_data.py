r"""Sanity-check web/data.json: FX, layer aggregates, and a sample company."""
import json

from emi.config import ROOT


def pct(x):
    return f"{x*100:5.1f}%" if isinstance(x, (int, float)) else "  n/a"


def b(x):
    return f"${x/1e9:,.0f}B" if isinstance(x, (int, float)) else "n/a"


data = json.loads((ROOT / "web" / "data.json").read_text(encoding="utf-8"))
print(f"as_of={data['as_of']}  companies={data['n_companies']}")
print(f"FX to USD: {data['fx']}\n")

print("LAYER / SUBLAYER AGGREGATES")
for L in data["layers"]:
    a = L["agg"]
    print(f"  {L['layer']:3s} {L['layer_name'][:30]:30s} n={L['n_companies']:3d} "
          f"rev={b(a['revenue_usd']):>8s} yoy={pct(a['revenue_yoy'])} qoq={pct(a['revenue_qoq'])} "
          f"gm={pct(a['gross_margin'])} om={pct(a['operating_margin'])} grow={pct(a['pct_growing'])}")
    for s in L["sublayers"]:
        sa = s["agg"]
        print(f"        {s['sublayer']:4s} {s['sublayer_name'][:26]:26s} n={s['n_companies']:2d} "
              f"rev={b(sa['revenue_usd']):>8s} yoy={pct(sa['revenue_yoy'])} "
              f"consensus_nextQ={b(sa['consensus_next_q_usd'])}")

for tk in ("NVDA", "2330.TW"):
    c = next((x for x in data["companies"] if x["ticker"] == tk), None)
    if not c:
        continue
    m = c["metrics"]
    print(f"\n{tk} — {c['name']} [{c['layer']}/{c['sublayer']}] {c['currency']}")
    print(f"  revenue {b(m['revenue']['usd'])} QoQ={pct(m['revenue']['qoq'])} YoY={pct(m['revenue']['yoy'])}")
    print(f"  gross_margin={pct(m['gross_margin']['value'])} op_margin={pct(m['operating_income']['margin'])}")
    print(f"  inventory_days={m['inventory_days']['value']} capex={b(m['capex']['usd'])}")
    rc = c["consensus"].get("revenue", {})
    print(f"  consensus rev: thisQ={b(rc.get('this_q_usd'))} (YoY {pct(rc.get('this_q_yoy'))}, QoQ {pct(rc.get('this_q_qoq'))})"
          f"  nextQ={b(rc.get('next_q_usd'))} (YoY {pct(rc.get('next_q_yoy'))})  analysts={rc.get('num_analysts')}")
    print(f"  series quarters: {c['series']['periods']}")
