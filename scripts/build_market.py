r"""Assemble web/market.json from market_series (WSTS + ECIA + SEMI) for the Market view.

Emits the FULL WSTS history (1986->) so the front-end can offer 5/10/15/20/30y ranges,
quarterly billings + quarterly YoY per region, and up/down-cycle duration statistics.

    $env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe scripts\build_market.py
"""
import json
import sqlite3

from emi.config import DB_PATH, ROOT

REGIONS = ["worldwide", "americas", "europe", "japan", "asiapacific"]
REGION_LABELS = {"worldwide": "Worldwide", "americas": "Americas", "europe": "Europe",
                 "japan": "Japan", "asiapacific": "Asia Pacific"}


def series_map(conn, name):
    return {p: v for p, v in conn.execute(
        "SELECT period, value FROM market_series WHERE series=? ORDER BY period", (name,)).fetchall()}


def shift_q(period, k):  # 'YYYYQn' minus k quarters
    y, q = int(period[:4]), int(period[5])
    idx = y * 4 + (q - 1) - k
    return f"{idx // 4}Q{idx % 4 + 1}"


UP_THR = 0.01    # YoY above +1% => up-cycle
DOWN_THR = -0.01  # YoY below -1% => down-cycle; in between = transition (neither)


def cycle_stats(quarters, yoy):
    """Up/down-cycle = consecutive quarters of worldwide YoY above +1% / below -1%.
    Quarters within +/-1% are transitions and belong to neither run (they break a run)."""
    seq = [v for v in yoy if v is not None]
    if not seq:
        return {}

    def cls(v):
        return "up" if v > UP_THR else "down" if v < DOWN_THR else "flat"

    runs = []  # (class, length) for every maximal same-class stretch
    cur, n = cls(seq[0]), 1
    for v in seq[1:]:
        c = cls(v)
        if c == cur:
            n += 1
        else:
            runs.append((cur, n)); cur, n = c, 1
    runs.append((cur, n))

    cur_run = runs[-1]            # current (possibly ongoing) stretch
    completed = runs[:-1]         # exclude the ongoing run from averages
    ups = [n for d, n in completed if d == "up"]
    downs = [n for d, n in completed if d == "down"]
    ups_all = [n for d, n in runs if d == "up"]
    downs_all = [n for d, n in runs if d == "down"]

    def avg(xs):
        return round(sum(xs) / len(xs), 1) if xs else None

    last = seq[-1]
    prev = seq[-2] if len(seq) >= 2 else None
    pos, acc = last > UP_THR, (prev is None or last >= prev)
    phase = ("Expansion" if pos and acc else "Slowing" if pos else "Recovery" if acc else "Downturn")
    return {
        "phase": phase,
        "last_yoy": round(last, 4),
        "current_dir": cur_run[0],
        "current_run_q": cur_run[1],
        "avg_up_q": avg(ups),
        "avg_down_q": avg(downs),
        "longest_up_q": max(ups_all) if ups_all else None,
        "longest_down_q": max(downs_all) if downs_all else None,
        "n_up": len(ups),
        "n_down": len(downs),
        "threshold_pct": 1,
    }


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    bq = {r: series_map(conn, f"billings_{r}_q") for r in REGIONS}
    ecia = series_map(conn, "book_to_bill")
    semi = series_map(conn, "na_billings")
    dram = series_map(conn, "dram_revenue")
    nand = series_map(conn, "nand_revenue")
    conn.close()

    quarters = sorted(bq["worldwide"])

    def yoy_arr(d):
        out = []
        for p in quarters:
            cur, prev = d.get(p), d.get(shift_q(p, 4))
            out.append(round(cur / prev - 1, 4) if (cur and prev) else None)
        return out

    billings_q = {r: [round(bq[r].get(p) or 0) for p in quarters] for r in REGIONS}
    yoy_q = {r: yoy_arr(bq[r]) for r in REGIONS}
    cyc = cycle_stats(quarters, yoy_q["worldwide"])

    out = {
        "as_of": quarters[-1] if quarters else None,
        "regions": REGIONS,
        "region_labels": REGION_LABELS,
        "quarters": quarters,
        "billings_q": billings_q,
        "yoy_q": yoy_q,
        "cycle": cyc,
        "ecia": {"months": sorted(ecia), "book_to_bill": [ecia[p] for p in sorted(ecia)]},
        "semi": {"months": sorted(semi), "na_billings": [round(semi[p]) for p in sorted(semi)]},
        "memory": {"quarters": sorted(dram),
                   "dram": [round(dram[p]) for p in sorted(dram)],
                   "nand": [round(nand.get(p, 0)) for p in sorted(dram)]},
        "seeded": ["ecia", "semi"],
        "sourced": {"memory": "TrendForce (DRAM + NAND industry revenue)"},
    }
    (ROOT / "web" / "market.json").write_text(json.dumps(out), encoding="utf-8")
    ww_last = billings_q["worldwide"][-1]
    print(f"wrote market.json | quarters={len(quarters)} ({quarters[0]}..{quarters[-1]}) | "
          f"phase={cyc.get('phase')} | last WW ${ww_last/1e9:.1f}B/q | YoY {yoy_q['worldwide'][-1]} | "
          f"avg up {cyc.get('avg_up_q')}Q / down {cyc.get('avg_down_q')}Q | "
          f"now {cyc.get('current_dir')} {cyc.get('current_run_q')}Q")


if __name__ == "__main__":
    main()
