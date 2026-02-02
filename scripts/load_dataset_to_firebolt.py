r"""
Load CSV files from ./dataset into Firebolt tables.

Usage:
  python .\scripts\load_dataset_to_firebolt.py --mode replace
  python .\scripts\load_dataset_to_firebolt.py --mode append
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

# Allow running from scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from firebolt_utils import connect_firebolt, get_firebolt_settings


TABLES = {
    "customers": ["customer_id", "first_name", "last_name", "email", "signup_date"],
    "products": ["product_id", "product_name", "category", "price", "cost"],
    "orders": ["order_id", "customer_id", "order_date", "total_amount", "city", "country"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "item_price", "purchase_price"],
    "page_views": ["event_id", "customer_id", "page_url", "event_time", "session_id"],
}

# Backward-compatible optional columns (older CSV/Excel may not include them).
OPTIONAL_COLS = {
    "products": ["cost"],
    "orders": ["city", "country"],
    "order_items": ["purchase_price"],
}


def _chunks(it: Iterable[list[str]], size: int) -> Iterable[list[list[str]]]:
    batch: list[list[str]] = []
    for row in it:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert_batch(cursor, table: str, cols: list[str], batch: list[list[str]]) -> None:
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT INTO public.{table} ({col_list}) VALUES ({placeholders})"
    cursor.executemany(sql, batch)


def load_table(cursor, dataset_dir: Path, table: str, mode: str, chunk_size: int) -> int:
    cols = TABLES[table]
    csv_path = dataset_dir / f"{table}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing dataset file: {csv_path}")

    if mode == "replace":
        cursor.execute(f"TRUNCATE TABLE public.{table}")

    incremental_key = None
    if mode == "incremental":
        # Simple watermark-based incremental loading:
        # - orders: order_id
        # - order_items: order_item_id
        # - page_views: event_id
        default_keys = {"orders": "order_id", "order_items": "order_item_id", "page_views": "event_id"}
        incremental_key = default_keys.get(table)
        if not incremental_key:
            raise ValueError(f"Incremental mode not supported for table `{table}`")

        cursor.execute(f"SELECT COALESCE(MAX({incremental_key}), 0) AS mx FROM public.{table}")
        mx = cursor.fetchone()[0]
        mx = int(mx) if mx is not None else 0
    else:
        mx = None

    total = 0
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = [c for c in cols if c not in OPTIONAL_COLS.get(table, [])]
        missing_cols = [c for c in required if c not in (reader.fieldnames or [])]
        if missing_cols:
            raise ValueError(f"{csv_path.name} is missing columns: {missing_cols}")

        if incremental_key:
            def _rows():
                for row in reader:
                    try:
                        if int(row[incremental_key]) <= mx:
                            continue
                    except Exception:
                        # if parsing fails, skip row
                        continue
                    yield [row[c] for c in cols]
            rows = _rows()
        else:
            def _rows_all():
                for row in reader:
                    # Fill optional columns with empty strings -> inserts NULL for missing values.
                    for c in OPTIONAL_COLS.get(table, []):
                        if c not in row or row[c] is None:
                            row[c] = ""
                    yield [row.get(c, "") for c in cols]
            rows = _rows_all()
        for batch in _chunks(rows, chunk_size):
            _insert_batch(cursor, table, cols, batch)
            total += len(batch)
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["append", "replace", "incremental"], default="replace")
    ap.add_argument("--dataset-dir", default=str(PROJECT_ROOT / "dataset"))
    ap.add_argument("--chunk-size", type=int, default=5000)
    ap.add_argument(
        "--tables",
        default="customers,products,orders,order_items,page_views",
        help="Comma-separated list of tables to load (default: all project tables)",
    )
    args = ap.parse_args()

    s = get_firebolt_settings()
    print(f"🔗 Loading dataset into Firebolt (db={s.get('database')}, engine={s.get('engine_name')})")

    dataset_dir = Path(args.dataset_dir)
    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    unknown = [t for t in tables if t not in TABLES]
    if unknown:
        raise SystemExit(f"Unknown tables: {unknown}. Valid: {list(TABLES.keys())}")

    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        for table in tables:
            print(f"\n➡ Loading {table} from {dataset_dir / (table + '.csv')} (mode={args.mode})")
            n = load_table(cur, dataset_dir, table, args.mode, args.chunk_size)
            print(f"✅ Inserted {n:,} rows into public.{table}")

        # quick validation
        print("\n=== Row counts ===")
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM public.{table}")
            cnt = int(cur.fetchone()[0])
            print(f"{table}: {cnt:,}")
    finally:
        cur.close()
        conn.close()

    print("\n🏁 Done.")


if __name__ == "__main__":
    main()


