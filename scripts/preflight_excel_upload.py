"""
Preflight check: validate that an Excel workbook can be split into dataset/*.csv
matching the project's schema.

Usage (PowerShell):
  python .\\scripts\\preflight_excel_upload.py .\\dataset\\sample_upload_template_realistic.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Ensure project root is importable when running this script directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.load_dataset_to_firebolt import TABLES  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python .\\scripts\\preflight_excel_upload.py <path-to-xlsx>")

    xlsx = Path(sys.argv[1]).resolve()
    if not xlsx.exists():
        raise SystemExit(f"Missing file: {xlsx}")

    xls = pd.ExcelFile(xlsx)
    sheets_lower = {s.lower(): s for s in xls.sheet_names}

    print("Excel:", xlsx)
    print("Sheets:", xls.sheet_names)

    missing_sheets = [t for t in TABLES.keys() if t.lower() not in sheets_lower]
    if missing_sheets:
        print("Missing required sheets:", missing_sheets)

    out_dir = xlsx.parent / "_upload_split_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    for table, cols in TABLES.items():
        sheet = sheets_lower.get(table.lower())
        if not sheet:
            continue
        df = pd.read_excel(xls, sheet_name=sheet)
        missing_cols = [c for c in cols if c not in df.columns]
        if missing_cols:
            errors.append(f"{table}: missing columns {missing_cols}")
            continue
        df = df[cols]
        csv_path = out_dir / f"{table}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        df2 = pd.read_csv(csv_path)
        if list(df2.columns) != cols:
            errors.append(f"{table}: header mismatch after write/read: {list(df2.columns)}")
        print(f"OK {table}: rows={len(df2):,} -> {csv_path}")

    if errors:
        print("\nERRORS:")
        for e in errors:
            print("-", e)
        raise SystemExit(1)

    if missing_sheets:
        print("\nNOTE: Missing some sheets. The app will still split any sheets that exist.")
    print("\nSUCCESS: Workbook can be split into schema-correct CSVs.")


if __name__ == "__main__":
    main()


