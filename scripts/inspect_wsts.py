r"""Inspect the WSTS HBR workbook structure."""
import pandas as pd

from emi.config import RAW_DIR

fp = RAW_DIR / "wsts" / "hbr.xlsx"
xl = pd.ExcelFile(fp)
print("SHEETS:", xl.sheet_names, "\n")
for s in xl.sheet_names:
    df = pd.read_excel(fp, sheet_name=s, header=None)
    print(f"==== '{s}'  shape={df.shape} ====")
    print(df.iloc[:14, :12].to_string(max_colwidth=18))
    print()
