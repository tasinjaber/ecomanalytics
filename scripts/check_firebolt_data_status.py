"""
Quick diagnostics for Firebolt data: counts + whether city/page_views data exists.

Usage:
  python .\\scripts\\check_firebolt_data_status.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.firebolt_conn import connect_firebolt  # noqa: E402


def _scalar(cur, sql: str):
    cur.execute(sql)
    return cur.fetchone()[0]


def main() -> None:
    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        print("orders:", _scalar(cur, "SELECT COUNT(*) FROM public.orders"))
        print("order_items:", _scalar(cur, "SELECT COUNT(*) FROM public.order_items"))
        print("page_views:", _scalar(cur, "SELECT COUNT(*) FROM public.page_views"))
        print("customers:", _scalar(cur, "SELECT COUNT(*) FROM public.customers"))
        print("products:", _scalar(cur, "SELECT COUNT(*) FROM public.products"))

        # City diagnostics (if column exists)
        try:
            empty = _scalar(cur, "SELECT COUNT(*) FROM public.orders WHERE city IS NULL OR city = ''")
            print("orders.city empty:", empty)
            cur.execute(
                "SELECT DISTINCT city FROM public.orders WHERE city IS NOT NULL AND city <> '' ORDER BY city LIMIT 20"
            )
            cities = [r[0] for r in cur.fetchall()]
            print("sample cities:", cities)
        except Exception as e:
            print("city check failed:", repr(e))
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()


