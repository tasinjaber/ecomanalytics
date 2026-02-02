from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class DashboardStats:
    customers: int
    products: int
    orders: int
    order_items: int
    page_views: int
    revenue_total: float


@dataclass(frozen=True)
class BusinessKpis:
    conversion_rate: float
    avg_order_value: float
    repeat_rate: float
    clv_simple: float


def _fetch_df(cursor, sql: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description] if cursor.description else []
    return pd.DataFrame(rows, columns=cols)


def get_stats(cursor) -> DashboardStats:
    counts = {}
    for table in ["customers", "products", "orders", "order_items", "page_views"]:
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM public.{table}")
        counts[table] = int(cursor.fetchone()[0])

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) AS revenue_total FROM public.orders")
    revenue_total = float(cursor.fetchone()[0])

    return DashboardStats(
        customers=counts["customers"],
        products=counts["products"],
        orders=counts["orders"],
        order_items=counts["order_items"],
        page_views=counts["page_views"],
        revenue_total=revenue_total,
    )


def get_orders_timeseries(cursor) -> pd.DataFrame:
    # Firebolt supports DATE_TRUNC for timestamps.
    return _fetch_df(
        cursor,
        """
        SELECT
          DATE_TRUNC('day', order_date) AS day,
          COUNT(*) AS orders,
          SUM(total_amount) AS revenue
        FROM public.orders
        GROUP BY 1
        ORDER BY 1
        """,
    )


def get_top_products(cursor, limit: int = 10) -> pd.DataFrame:
    return _fetch_df(
        cursor,
        """
        SELECT
          p.product_id,
          p.product_name,
          p.category,
          SUM(oi.quantity) AS units_sold,
          SUM(oi.quantity * oi.item_price) AS sales
        FROM public.order_items oi
        JOIN public.products p ON p.product_id = oi.product_id
        GROUP BY 1,2,3
        ORDER BY sales DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_top_pages(cursor, limit: int = 10) -> pd.DataFrame:
    return _fetch_df(
        cursor,
        """
        SELECT
          page_url,
          COUNT(*) AS views
        FROM public.page_views
        GROUP BY 1
        ORDER BY views DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_page_views_sample(cursor, limit: int = 50) -> pd.DataFrame:
    return _fetch_df(
        cursor,
        """
        SELECT
          event_id,
          customer_id,
          page_url,
          event_time,
          session_id
        FROM public.page_views
        ORDER BY event_time DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_business_kpis(cursor) -> BusinessKpis:
    """
    Business KPIs derived from existing tables (simple formulas for coursework/demo).
    - conversion_rate = orders / unique sessions (from page_views.session_id)
    - AOV = total revenue / orders
    - repeat_rate = repeat customers / customers with orders
    - CLV (simple) = AOV * avg_orders_per_customer * repeat_rate
    """
    cursor.execute("SELECT COUNT(*) FROM public.orders")
    orders = int(cursor.fetchone()[0])

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM public.orders")
    revenue = float(cursor.fetchone()[0])

    cursor.execute("SELECT COUNT(DISTINCT session_id) FROM public.page_views")
    sessions = int(cursor.fetchone()[0])

    cursor.execute(
        """
        WITH per_customer AS (
          SELECT customer_id, COUNT(*) AS order_count
          FROM public.orders
          GROUP BY customer_id
        )
        SELECT
          COUNT(*) AS customers_with_orders,
          SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
          AVG(order_count) AS avg_orders_per_customer
        FROM per_customer
        """
    )
    cwo, repeat_customers, avg_orders_per_customer = cursor.fetchone()
    cwo = int(cwo or 0)
    repeat_customers = int(repeat_customers or 0)
    avg_orders_per_customer = float(avg_orders_per_customer or 0.0)

    # Conversion rate is a proxy; clamp to [0, 1] to keep it interpretable as a percentage.
    conversion_rate = (orders / sessions) if sessions > 0 else 0.0
    conversion_rate = max(0.0, min(conversion_rate, 1.0))
    aov = (revenue / orders) if orders > 0 else 0.0
    repeat_rate = (repeat_customers / cwo) if cwo > 0 else 0.0
    clv_simple = aov * avg_orders_per_customer * repeat_rate

    return BusinessKpis(
        conversion_rate=conversion_rate,
        avg_order_value=aov,
        repeat_rate=repeat_rate,
        clv_simple=clv_simple,
    )


def get_customers(cursor, limit: int = 200) -> pd.DataFrame:
    return _fetch_df(
        cursor,
        """
        SELECT
          customer_id,
          first_name,
          last_name,
          email,
          signup_date
        FROM public.customers
        ORDER BY customer_id
        LIMIT %s
        """,
        (limit,),
    )


def get_customer_rfm(cursor, lookback_days: int = 365, limit: int = 5000) -> pd.DataFrame:
    """
    RFM = Recency/Frequency/Monetary per customer for segmentation.
    """
    lookback_days = int(lookback_days)
    limit = int(limit)
    return _fetch_df(
        cursor,
        f"""
        WITH o AS (
          SELECT customer_id, order_date, total_amount
          FROM public.orders
          WHERE order_date >= NOW() - INTERVAL '{lookback_days} days'
        ),
        agg AS (
          SELECT
            customer_id,
            MAX(order_date) AS last_order,
            COUNT(*) AS frequency,
            SUM(total_amount) AS monetary
          FROM o
          GROUP BY customer_id
        )
        SELECT
          customer_id,
          DATE_DIFF('day', last_order, NOW()) AS recency_days,
          frequency,
          monetary,
          CASE WHEN frequency > 0 THEN monetary / frequency ELSE 0 END AS avg_order_value
        FROM agg
        ORDER BY monetary DESC
        LIMIT %s
        """,
        (limit,),
    )


def get_products_catalog(cursor, limit: int = 5000) -> pd.DataFrame:
    return _fetch_df(
        cursor,
        """
        SELECT product_id, product_name, category
        FROM public.products
        ORDER BY product_id
        LIMIT %s
        """,
        (int(limit),),
    )


def get_order_items_for_recommendations(cursor, lookback_days: int = 180, limit: int = 200_000) -> pd.DataFrame:
    """
    Minimal input for 'also bought' recommendations: (order_id, product_id).
    """
    lookback_days = int(lookback_days)
    limit = int(limit)
    return _fetch_df(
        cursor,
        f"""
        SELECT
          oi.order_id,
          oi.product_id
        FROM public.order_items oi
        JOIN public.orders o ON o.order_id = oi.order_id
        WHERE o.order_date >= NOW() - INTERVAL '{lookback_days} days'
        LIMIT %s
        """,
        (limit,),
    )


def get_city_daily_timeseries(cursor, limit_days: int = 365) -> pd.DataFrame:
    """
    Daily orders/revenue by city for location-based growth + forecasting.
    Requires orders.city to be populated.
    Revenue is computed from orders.total_amount (must be accurate).
    """
    limit_days = int(limit_days)
    return _fetch_df(
        cursor,
        f"""
        SELECT
          DATE_TRUNC('day', order_date) AS day,
          COALESCE(NULLIF(city,''), 'Unknown') AS city,
          COUNT(*) AS orders,
          SUM(total_amount) AS revenue
        FROM public.orders
        WHERE order_date >= NOW() - INTERVAL '{limit_days} days'
        GROUP BY 1,2
        ORDER BY 1,2
        """,
    )


def get_category_daily_timeseries(cursor, limit_days: int = 365) -> pd.DataFrame:
    """
    Daily units/revenue by product category for marketing budget decisions.
    Revenue computed from order_items (quantity * item_price).
    """
    limit_days = int(limit_days)
    return _fetch_df(
        cursor,
        f"""
        SELECT
          DATE_TRUNC('day', o.order_date) AS day,
          COALESCE(p.category, 'Unknown') AS category,
          SUM(oi.quantity) AS units,
          SUM(oi.quantity * oi.item_price) AS revenue
        FROM public.order_items oi
        JOIN public.orders o ON o.order_id = oi.order_id
        LEFT JOIN public.products p ON p.product_id = oi.product_id
        WHERE o.order_date >= NOW() - INTERVAL '{limit_days} days'
        GROUP BY 1,2
        ORDER BY 1,2
        """,
    )


