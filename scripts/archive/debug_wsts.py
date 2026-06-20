r"""Print recent-year blocks of the WSTS workbook to debug parsing."""
import pandas as pd

from emi.config import RAW_DIR

fp = RAW_DIR / "wsts" / "hbr.xlsx"
for sheet in ["Monthly Data", "3MMA"]:
    df = pd.read_excel(fp, sheet_name=sheet, header=None)
    print(f"\n##### {sheet}  shape={df.shape} #####")
    # header (row 3) full width
    print("HEADER row3:", [str(x)[:9] for x in df.iloc[3].tolist()])
    for yr in [2024, 2025, 2026]:
        idx = df.index[df.iloc[:, 0].apply(lambda x: str(x).strip() == str(yr))]
        if len(idx) == 0:
            continue
        i = idx[0]
        print(f"\n-- year {yr} (rows {i}..{i+5}) --")
        blk = df.iloc[i:i+6]
        for _, r in blk.iterrows():
            print("  ", [str(x)[:10] for x in r.tolist()])
