r"""Verify WSTS series in market_series."""
import sqlite3

from emi.config import DB_PATH

c = sqlite3.connect(str(DB_PATH))
series = [r[0] for r in c.execute("SELECT DISTINCT series FROM market_series WHERE source='wsts' ORDER BY series")]
print("series:", series)
wwq = c.execute("SELECT period, value FROM market_series WHERE series='billings_worldwide_q' ORDER BY period DESC LIMIT 4").fetchall()
print("worldwide quarterly (latest 4):", [(p, round(v / 1e9, 1)) for p, v in wwq])
a24 = c.execute("SELECT SUM(value) FROM market_series WHERE series='billings_worldwide' AND period LIKE '2024-%'").fetchone()[0]
a25 = c.execute("SELECT SUM(value) FROM market_series WHERE series='billings_worldwide' AND period LIKE '2025-%'").fetchone()[0]
print(f"2024 worldwide annual (sum of months): ${a24/1e9:.1f}B  (real WSTS 2024 ≈ $627B)")
print(f"2025 worldwide annual (sum of months): ${a25/1e9:.1f}B")
c.close()
