from __future__ import annotations

# Allow running this file directly (`python .\report\generate_report.py`)
# by ensuring the project root is on sys.path.
import sys
from pathlib import Path as _Path

_PROJECT_ROOT = _Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json
from datetime import datetime, timezone
from pathlib import Path

import altair as alt
import pandas as pd

from dashboard.queries import (
    get_customers,
    get_orders_timeseries,
    get_stats,
    get_top_pages,
    get_top_products,
)
from firebolt_utils import connect_firebolt, get_firebolt_settings


def _kpi_row(stats) -> str:
    def kpi(label: str, value: str) -> str:
        return f"""
        <div class="kpi">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
        </div>
        """

    return "\n".join(
        [
            kpi("Customers", f"{stats.customers:,}"),
            kpi("Products", f"{stats.products:,}"),
            kpi("Orders", f"{stats.orders:,}"),
            kpi("Order items", f"{stats.order_items:,}"),
            kpi("Page views", f"{stats.page_views:,}"),
            kpi("Revenue (orders total, €)", f"€{stats.revenue_total:,.2f}"),
        ]
    )


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p><em>No data</em></p>"
    return df.to_html(index=False, classes="table", border=0)


def _chart_specs(ts: pd.DataFrame) -> tuple[dict, dict]:
    if ts.empty:
        return {}, {}

    ts2 = ts.copy()
    ts2["day"] = pd.to_datetime(ts2["day"])

    orders_chart = (
        alt.Chart(ts2)
        .mark_line(point=True)
        .encode(
            x=alt.X("day:T", title="Day"),
            y=alt.Y("orders:Q", title="Orders"),
            tooltip=["day:T", "orders:Q"],
        )
        .properties(height=260)
    )

    revenue_chart = (
        alt.Chart(ts2)
        .mark_line(point=True, color="#2E7D32")
        .encode(
            x=alt.X("day:T", title="Day"),
            y=alt.Y("revenue:Q", title="Revenue (€)"),
            tooltip=["day:T", alt.Tooltip("revenue:Q", title="Revenue (€)", format=",.2f")],
        )
        .properties(height=260)
    )

    return orders_chart.to_dict(), revenue_chart.to_dict()


def generate_report(output_path: Path) -> Path:
    s = get_firebolt_settings()
    conn = connect_firebolt()
    cur = conn.cursor()

    try:
        stats = get_stats(cur)
        ts = get_orders_timeseries(cur)
        top_products = get_top_products(cur, limit=10)
        top_pages = get_top_pages(cur, limit=10)
        customers = get_customers(cur, limit=200)
    finally:
        cur.close()
        conn.close()

    orders_spec, revenue_spec = _chart_specs(ts)

    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Firebolt E-commerce Report</title>
    <style>
      body {{
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
        margin: 24px;
        color: #111827;
        background: #ffffff;
      }}
      .meta {{
        color: #6b7280;
        margin-top: 6px;
        margin-bottom: 18px;
      }}
      .kpis {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 12px;
        margin: 16px 0 22px;
      }}
      .kpi {{
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px;
        background: #fafafa;
      }}
      .kpi-label {{
        font-size: 12px;
        color: #6b7280;
        margin-bottom: 6px;
      }}
      .kpi-value {{
        font-size: 20px;
        font-weight: 700;
      }}
      h2 {{
        margin-top: 28px;
        margin-bottom: 10px;
      }}
      .grid2 {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
      }}
      .card {{
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 14px;
      }}
      .table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }}
      .table th, .table td {{
        border-bottom: 1px solid #e5e7eb;
        padding: 8px 10px;
        text-align: left;
        vertical-align: top;
      }}
      .table th {{
        background: #f9fafb;
        font-weight: 600;
      }}
      .muted {{
        color: #6b7280;
      }}
      @media (max-width: 1100px) {{
        .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .grid2 {{ grid-template-columns: 1fr; }}
      }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  </head>
  <body>
    <h1>Firebolt E-commerce Report</h1>
    <div class="meta">
      Generated: <strong>{generated_at}</strong> ·
      Account: <code>{s.get("account_name")}</code> ·
      Database: <code>{s.get("database")}</code> ·
      Engine: <code>{s.get("engine_name")}</code>
    </div>

    <div class="kpis">
      {_kpi_row(stats)}
    </div>

    <h2>Overview</h2>
    <div class="grid2">
      <div class="card">
        <h3 style="margin: 0 0 8px">Orders by Day</h3>
        <div id="chart_orders" class="muted">No data</div>
      </div>
      <div class="card">
        <h3 style="margin: 0 0 8px">Revenue by Day</h3>
        <div id="chart_revenue" class="muted">No data</div>
      </div>
    </div>

    <h2>Top Products</h2>
    <div class="card">{_table(top_products)}</div>

    <h2>Top Pages</h2>
    <div class="card">{_table(top_pages)}</div>

    <h2>Customers (sample)</h2>
    <div class="card">{_table(customers)}</div>

    <script>
      const ordersSpec = {json.dumps(orders_spec)};
      const revenueSpec = {json.dumps(revenue_spec)};

      if (ordersSpec && Object.keys(ordersSpec).length) {{
        vegaEmbed("#chart_orders", ordersSpec, {{ actions: false }});
      }}
      if (revenueSpec && Object.keys(revenueSpec).length) {{
        vegaEmbed("#chart_revenue", revenueSpec, {{ actions: false }});
      }}
    </script>
  </body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "firebolt_report.html"
    path = generate_report(out)
    print(f"✅ Report written to: {path}")


