from __future__ import annotations

import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException

from firebolt_utils import connect_firebolt


app = FastAPI(title="Firebolt Analytics API", version="1.0.0")


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY is not set on the server.")
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _fetch_one(sql: str):
    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        row = cur.fetchone()
        cols = [c[0] for c in cur.description] if cur.description else []
        return dict(zip(cols, row)) if row and cols else {}
    finally:
        cur.close()
        conn.close()


def _fetch_many(sql: str, limit: int = 50):
    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in rows] if cols else []
    finally:
        cur.close()
        conn.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/kpis", dependencies=[Depends(require_api_key)])
def kpis():
    t0 = time.time()
    data = _fetch_one(
        """
        SELECT
          (SELECT COUNT(*) FROM public.customers)   AS customers,
          (SELECT COUNT(*) FROM public.products)    AS products,
          (SELECT COUNT(*) FROM public.orders)      AS orders,
          (SELECT COUNT(*) FROM public.order_items) AS order_items,
          (SELECT COUNT(*) FROM public.page_views)  AS page_views,
          (SELECT COALESCE(SUM(total_amount), 0) FROM public.orders) AS revenue_total_eur
        """
    )
    data["latency_ms"] = int((time.time() - t0) * 1000)
    return data


@app.get("/top-products", dependencies=[Depends(require_api_key)])
def top_products(limit: int = 10):
    return _fetch_many(
        """
        SELECT
          p.product_id,
          p.product_name,
          p.category,
          SUM(oi.quantity) AS units_sold,
          SUM(oi.quantity * oi.item_price) AS revenue_eur
        FROM public.order_items oi
        JOIN public.products p ON p.product_id = oi.product_id
        GROUP BY 1,2,3
        ORDER BY revenue_eur DESC
        LIMIT %s
        """,
        limit=max(1, min(100, int(limit))),
    )


@app.get("/top-pages", dependencies=[Depends(require_api_key)])
def top_pages(limit: int = 10):
    return _fetch_many(
        """
        SELECT
          page_url,
          COUNT(*) AS views
        FROM public.page_views
        GROUP BY 1
        ORDER BY views DESC
        LIMIT %s
        """,
        limit=max(1, min(100, int(limit))),
    )


