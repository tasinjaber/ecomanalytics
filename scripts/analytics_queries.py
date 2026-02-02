"""
Run a few analytical queries against Firebolt tables.

Note: This file is meant to be executed directly:
  python .\\scripts\\analytics_queries.py
So we ensure the project root is on sys.path.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from firebolt_utils import connect_firebolt, get_firebolt_settings


def run_query(cursor, title: str, sql: str) -> None:
    print(f"\n=== {title} ===")
    cursor.execute(sql)
    cols = [c[0] for c in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    if cols:
        print(" | ".join(cols))
        print("-" * max(20, len(" | ".join(cols))))
    for r in rows:
        print(r)


def main() -> None:
    s = get_firebolt_settings()
    print("🔗 Firebolt analytics runner")
    print(f"Account: {s.get('account_name')} | Database: {s.get('database')} | Engine: {s.get('engine_name')}")

    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        # 1) Total sales aggregation (from orders table)
        run_query(
            cur,
            "Total sales (SUM of orders.total_amount)",
            """
            SELECT
              COUNT(*) AS total_orders,
              COALESCE(SUM(total_amount), 0) AS total_sales
            FROM public.orders
            """,
        )

        # 2) Customer count + repeat customers (customers with > 1 order)
        run_query(
            cur,
            "Customer count + repeat customers",
            """
            WITH per_customer AS (
              SELECT customer_id, COUNT(*) AS order_count
              FROM public.orders
              GROUP BY customer_id
            )
            SELECT
              (SELECT COUNT(*) FROM public.customers) AS total_customers,
              COUNT(*) AS customers_with_orders,
              SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
              MAX(order_count) AS max_orders_by_one_customer
            FROM per_customer
            """,
        )

        # 3) Product-wise revenue (quantity * item_price)
        run_query(
            cur,
            "Product-wise revenue (Top 10)",
            """
            SELECT
              p.product_id,
              p.product_name,
              p.category,
              SUM(oi.quantity) AS units_sold,
              SUM(oi.quantity * oi.item_price) AS revenue
            FROM public.order_items oi
            JOIN public.products p ON p.product_id = oi.product_id
            GROUP BY 1,2,3
            ORDER BY revenue DESC
            LIMIT 10
            """,
        )
    finally:
        cur.close()
        conn.close()

    print("\n✅ Done.")


if __name__ == "__main__":
    main()


