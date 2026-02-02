import os
import sys
import time
import base64
import hashlib
import hmac
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import altair as alt
import math
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Optional deps for the SaaS-style UI (graceful fallback if missing)
try:
    import plotly.express as px  # type: ignore
except Exception:  # pragma: no cover
    px = None  # type: ignore

try:
    from st_aggrid import AgGrid, GridOptionsBuilder  # type: ignore
except Exception:  # pragma: no cover
    AgGrid = None  # type: ignore
    GridOptionsBuilder = None  # type: ignore

from auth import (
    authenticate,
    register_user,
    admin_create_user,
    admin_delete_user,
    admin_reset_password,
    admin_set_role,
    list_users_for_admin,
)
from firebolt_conn import connect_firebolt, get_firebolt_settings
from queries import (
    get_customers,
    get_orders_timeseries,
    get_page_views_sample,
    get_business_kpis,
    get_stats,
    get_top_pages,
    get_top_products,
    get_customer_rfm,
    get_order_items_for_recommendations,
    get_products_catalog,
    get_city_daily_timeseries,
    get_category_daily_timeseries,
)

# Optional ML deps (used in Decision Assistant / Insights page)
try:
    import numpy as np  # type: ignore
    from sklearn.cluster import KMeans  # type: ignore
    from sklearn.ensemble import IsolationForest  # type: ignore
    from sklearn.linear_model import Ridge  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore
    KMeans = None  # type: ignore
    IsolationForest = None  # type: ignore
    Ridge = None  # type: ignore

# Allow importing project-root modules and scripts when running via Streamlit.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_data import (
    ensure_dataset_dir,
    generate_customers,
    generate_orders_and_items,
    generate_page_views,
    generate_products,
)
from scripts.create_tables import create_tables
from scripts.load_dataset_to_firebolt import TABLES, load_table


st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "€").strip() or "€"


def _load_dotenv_if_present() -> None:
    """
    Minimal .env loader (so login 'remember me' and Firebolt settings work on refresh).
    Loads KEY=VALUE only if not already set.
    """
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_present()


def _auth_secret() -> bytes:
    # Stable secret recommended via .env:
    #   DASHBOARD_AUTH_SECRET=some_long_random_string
    s = (os.getenv("DASHBOARD_AUTH_SECRET") or os.getenv("ADMIN_INVITE_CODE") or "dev-secret-change-me").encode(
        "utf-8"
    )
    return s


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _make_login_token(user: dict, days_valid: int = 14) -> str:
    payload = {
        "u": user.get("username"),
        "r": user.get("role"),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=days_valid)).timestamp()),
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(_auth_secret(), body, hashlib.sha256).digest()
    return f"{_b64url(body)}.{_b64url(sig)}"


def _read_login_token(token: str) -> dict | None:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        body = _b64url_decode(body_b64)
        sig = _b64url_decode(sig_b64)
        expected = hmac.new(_auth_secret(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(body.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        u = payload.get("u")
        r = payload.get("r")
        if not u or not r:
            return None
        return {"username": str(u), "role": str(r)}
    except Exception:
        return None

st.markdown(
    """
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

  /* KPI cards */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0.25rem 0 0.75rem;
  }
  .kpi-card {
    border: 1px solid rgba(229,231,235,0.8);
    border-radius: 12px;
    padding: 12px 12px 10px;
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(6px);
  }
  .kpi-label {
    font-size: 12px;
    opacity: 0.75;
    margin-bottom: 6px;
  }
  .kpi-value {
    font-size: 20px;
    font-weight: 700;
    line-height: 1.15;
    word-break: break-word;
  }
  @media (max-width: 1200px) {
    .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  }
  @media (max-width: 700px) {
    .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def _get_conn():
    return connect_firebolt()


@st.cache_resource
def _ensure_schema_columns() -> None:
    """
    Lightweight schema upgrade so new dashboard features don't crash on older databases.
    Safe to call repeatedly (ADD COLUMN IF NOT EXISTS).
    """
    try:
        conn = _get_conn()
        cur = conn.cursor()
        try:
            # Orders: geo dimensions
            cur.execute("ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS city TEXT")
            cur.execute("ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS country TEXT")
            # Order items: purchase cost
            cur.execute("ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS purchase_price DOUBLE")
            # Products: cost baseline
            cur.execute("ALTER TABLE public.products ADD COLUMN IF NOT EXISTS cost DOUBLE")
        finally:
            cur.close()
    except Exception:
        # If ALTER fails (permissions/table missing), other code will handle gracefully.
        return


@st.cache_data(ttl=30)
def _load_all():
    conn = _get_conn()
    cur = conn.cursor()
    try:
        stats = get_stats(cur)
        biz = get_business_kpis(cur)
        ts = get_orders_timeseries(cur)
        top_products = get_top_products(cur, limit=10)
        top_pages = get_top_pages(cur, limit=10)
        page_views_sample = get_page_views_sample(cur, limit=50)
        customers = get_customers(cur, limit=200)
        return stats, biz, ts, top_products, top_pages, page_views_sample, customers
    finally:
        cur.close()


@st.cache_data(ttl=60)
def _load_rfm(lookback_days: int = 365, limit: int = 5000) -> pd.DataFrame:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        return get_customer_rfm(cur, lookback_days=int(lookback_days), limit=int(limit))
    finally:
        cur.close()


@st.cache_data(ttl=60)
def _load_reco_inputs(lookback_days: int = 180, limit: int = 200_000):
    conn = _get_conn()
    cur = conn.cursor()
    try:
        items = get_order_items_for_recommendations(cur, lookback_days=int(lookback_days), limit=int(limit))
        products = get_products_catalog(cur, limit=5000)
        return items, products
    finally:
        cur.close()


@st.cache_data(ttl=60)
def _load_city_ts(limit_days: int = 365) -> pd.DataFrame:
    _ensure_schema_columns()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        return get_city_daily_timeseries(cur, limit_days=int(limit_days))
    except Exception:
        # Missing columns / older schema / permissions, etc.
        return pd.DataFrame()
    finally:
        cur.close()


@st.cache_data(ttl=60)
def _load_category_ts(limit_days: int = 365) -> pd.DataFrame:
    _ensure_schema_columns()
    conn = _get_conn()
    cur = conn.cursor()
    try:
        return get_category_daily_timeseries(cur, limit_days=int(limit_days))
    except Exception:
        return pd.DataFrame()
    finally:
        cur.close()


def _fmt_money(x: float) -> str:
    return f"{CURRENCY_SYMBOL}{x:,.2f}"


def _fmt_money0(x: float) -> str:
    return f"{CURRENCY_SYMBOL}{x:,.0f}"


def _fmt_pct(x: float, digits: int = 0) -> str:
    x = float(x)
    if math.isnan(x):
        return "—"
    if digits <= 0:
        return f"{x:.0%}"
    return f"{x:.{int(digits)}%}"


def _fmt_pct_signed(x: float, digits: int = 0) -> str:
    x = float(x)
    if math.isnan(x):
        return "—"
    sign = "+" if x > 0 else ""
    if digits <= 0:
        return f"{sign}{x:.0%}"
    return f"{sign}{x:.{int(digits)}%}"


def _pct_change(curr: float, prev: float, non_negative: bool = True) -> float | None:
    """
    Percent change helper.
    - If prev == 0: returns None (meaning 'NEW' / not defined)
    - If non_negative: clamps minimum at -100% (because values can't go below 0)
    """
    try:
        curr = float(curr or 0.0)
        prev = float(prev or 0.0)
    except Exception:
        return None
    if prev <= 0:
        return None
    ch = (curr - prev) / prev
    if non_negative:
        ch = max(ch, -1.0)
    return ch


def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def _kpi_card(label: str, value: str) -> str:
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
    </div>
    """


st.markdown("## Dashboard")

with st.sidebar:
    st.subheader("Login")
    if "user" not in st.session_state:
        st.session_state["user"] = None

    # Auto-login from URL token (persists across browser refresh).
    if st.session_state["user"] is None:
        try:
            qp = st.query_params  # type: ignore[attr-defined]
            token = qp.get("auth", "")
        except Exception:
            token = (st.experimental_get_query_params() or {}).get("auth", [""])[0]  # type: ignore[attr-defined]
        if token:
            u = _read_login_token(token)
            if u:
                st.session_state["user"] = u

    if st.session_state["user"] is None:
        st.write("Welcome 👋")
        remember_me = st.checkbox("Remember me on this browser", value=True, key="login_remember_me")
        tab_login, tab_register = st.tabs(["Sign in", "Register"])

        with tab_login:
            u = st.text_input("Username", key="login_username")
            p = st.text_input("Password", type="password", key="login_password")
            if st.button("Sign in", key="login_btn"):
                user = authenticate(u.strip(), p)
                if not user:
                    st.error("Invalid username/password.")
                else:
                    st.session_state["user"] = {"username": user.username, "role": user.role}
                    if remember_me:
                        token = _make_login_token(st.session_state["user"])
                        try:
                            st.query_params["auth"] = token  # type: ignore[attr-defined]
                        except Exception:
                            st.experimental_set_query_params(auth=token)  # type: ignore[attr-defined]
                    st.success(f"Signed in as {user.username} ({user.role})")
                    st.rerun()

        with tab_register:
            st.caption("New users are created as **Viewer** by default.")
            ru = st.text_input("New username", key="reg_username")
            rp = st.text_input("New password", type="password", key="reg_password")
            rc = st.text_input("Confirm password", type="password", key="reg_confirm")
            st.caption("Password limit: **max 72 bytes** (bcrypt limitation).")

            # Optional invite to create higher roles (set ADMIN_INVITE_CODE in .env)
            invite = st.text_input("Admin invite code (optional)", type="password", key="reg_invite")
            allow_admin = bool(os.getenv("ADMIN_INVITE_CODE")) and invite == os.getenv("ADMIN_INVITE_CODE")
            role_choice = "Viewer"
            if allow_admin:
                role_choice = st.selectbox("Role", ["Viewer", "Analyst", "Admin"], index=0, key="reg_role")

            if st.button("Create account", key="reg_btn"):
                if rp != rc:
                    st.error("Passwords do not match.")
                else:
                    try:
                        user = register_user(ru, rp, role=role_choice)  # type: ignore[arg-type]
                        st.session_state["user"] = {"username": user.username, "role": user.role}
                        st.success(f"Account created. Signed in as {user.username} ({user.role})")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        st.stop()
    else:
        st.write(f"Welcome, **{st.session_state['user']['username']}** 👋")
        st.caption(f"Role: `{st.session_state['user']['role']}`")
        if st.button("Logout"):
            st.session_state["user"] = None
            try:
                # Clear token on logout.
                if hasattr(st, "query_params"):
                    st.query_params.clear()  # type: ignore[attr-defined]
                else:
                    st.experimental_set_query_params()  # type: ignore[attr-defined]
            except Exception:
                pass
            st.rerun()

role = st.session_state["user"]["role"]


try:
    stats, biz, ts, top_products, top_pages, page_views_sample, customers = _load_all()
except Exception as e:
    st.error("Failed to load data from Firebolt.")
    st.code(str(e))
    st.stop()


def _render_kpis() -> None:
    # KPI revenue window: last 30 days based on latest day in the dataset (not NOW()).
    try:
        _ts = ts.copy()
        _ts["day"] = pd.to_datetime(_ts["day"]).dt.normalize()
        _ts = _ts.sort_values("day")
        _end = _ts["day"].max()
        _start = _end - pd.Timedelta(days=29)
        _rev_30d = float(_ts[(_ts["day"] >= _start) & (_ts["day"] <= _end)]["revenue"].sum())
    except Exception:
        _rev_30d = 0.0

    html = f"""
    <style>
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        color: #f9fafb;
      }}
      .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 12px;
        padding: 2px 2px 6px;
      }}
      .kpi-card {{
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 14px;
        padding: 12px 12px 10px;
        background: rgba(255,255,255,0.04);
      }}
      .kpi-label {{
        font-size: 12px;
        color: rgba(226,232,240,0.85);
        margin-bottom: 6px;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }}
      .kpi-value {{
        font-size: 20px;
        font-weight: 800;
        line-height: 1.15;
        word-break: break-word;
        color: #f8fafc;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }}
      @media (max-width: 1200px) {{
        .kpi-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      }}
      @media (max-width: 700px) {{
        .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      }}
    </style>
    <div class="kpi-grid">
      {_kpi_card("Customers", f"{stats.customers:,}")}
      {_kpi_card("Products", f"{stats.products:,}")}
      {_kpi_card("Orders", f"{stats.orders:,}")}
      {_kpi_card("Order items", f"{stats.order_items:,}")}
      {_kpi_card("Page views", f"{stats.page_views:,}")}
      {_kpi_card("Total revenue", _fmt_money(stats.revenue_total))}
    </div>
    """
    # Use a component so HTML never gets escaped as markdown text.
    # Height is intentionally generous so cards don't get clipped when wrapping.
    components.html(html, height=220, scrolling=False)


_render_kpis()

st.caption("")  # (Intentionally blank) keep layout spacing without extra KPI text.

st.divider()

def _monthly_revenue(ts_df: pd.DataFrame) -> pd.DataFrame:
    if ts_df.empty:
        return pd.DataFrame(columns=["month", "revenue"])
    ts2 = ts_df.copy()
    ts2["day"] = pd.to_datetime(ts2["day"])
    ts2["month"] = ts2["day"].dt.to_period("M").dt.to_timestamp()
    out = ts2.groupby("month", as_index=False)["revenue"].sum()
    return out.sort_values("month")


def _last_7d_insights(ts_df: pd.DataFrame) -> dict[str, float]:
    """
    Compute simple, explainable insights from the daily orders/revenue timeseries.
    Uses the *latest dates available in the dataset* (not NOW()).
    """
    if ts_df.empty:
        return {"rev_7d": 0.0, "rev_prev_7d": 0.0, "orders_7d": 0.0, "orders_prev_7d": 0.0}
    df = ts_df.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df = df.sort_values("day")
    end = df["day"].max()
    start_7 = end - pd.Timedelta(days=6)
    start_prev = start_7 - pd.Timedelta(days=7)
    end_prev = start_7 - pd.Timedelta(days=1)
    w7 = df[(df["day"] >= start_7) & (df["day"] <= end)]
    wprev = df[(df["day"] >= start_prev) & (df["day"] <= end_prev)]
    return {
        "rev_7d": float(w7["revenue"].sum()),
        "rev_prev_7d": float(wprev["revenue"].sum()),
        "orders_7d": float(w7["orders"].sum()),
        "orders_prev_7d": float(wprev["orders"].sum()),
    }


def _last_nd_window(ts_df: pd.DataFrame, n_days: int = 30) -> dict[str, float]:
    """
    Sum revenue + orders over the last N days present in the dataset (as-of max day).
    """
    if ts_df.empty:
        return {"revenue": 0.0, "orders": 0.0}
    n_days = int(max(1, min(int(n_days), 365)))
    df = ts_df.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df = df.sort_values("day")
    end = df["day"].max()
    start = end - pd.Timedelta(days=n_days - 1)
    w = df[(df["day"] >= start) & (df["day"] <= end)]
    return {"revenue": float(w["revenue"].sum()), "orders": float(w["orders"].sum())}


@st.cache_data(ttl=60)
def _units_sold_last_nd(n_days: int = 30) -> int:
    """
    Units sold over last N days (relative to latest order_date in the dataset).
    """
    n_days = int(max(1, min(int(n_days), 365)))
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            WITH asof AS (SELECT MAX(order_date) AS as_of FROM public.orders)
            SELECT COALESCE(SUM(oi.quantity), 0) AS units
            FROM public.order_items oi
            JOIN public.orders o ON o.order_id = oi.order_id
            CROSS JOIN asof a
            WHERE o.order_date >= a.as_of - INTERVAL '{n_days} days'
            """
        )
        return int(cur.fetchone()[0] or 0)
    finally:
        cur.close()


def _forecast_series_next_days(daily_df: pd.DataFrame, y_col: str, horizon_days: int = 30) -> pd.DataFrame:
    """
    Generic forecast helper for a daily series using the same simple model as revenue forecasting.
    Returns df with columns: day, yhat
    """
    if np is None or Ridge is None:
        return pd.DataFrame()
    if daily_df.empty or y_col not in daily_df.columns:
        return pd.DataFrame()

    df = daily_df.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df = df.sort_values("day")
    df["t"] = (df["day"] - df["day"].min()).dt.days.astype(int)
    df["dow"] = df["day"].dt.dayofweek.astype(int)
    X = pd.get_dummies(df[["t", "dow"]], columns=["dow"], drop_first=False)
    y = pd.to_numeric(df[y_col], errors="coerce").fillna(0.0).to_numpy()

    model = Ridge(alpha=1.0)
    model.fit(X.to_numpy(), y)

    future_days = pd.date_range(df["day"].max() + pd.Timedelta(days=1), periods=int(horizon_days), freq="D")
    f = pd.DataFrame({"day": future_days})
    f["t"] = (f["day"] - df["day"].min()).dt.days.astype(int)
    f["dow"] = f["day"].dt.dayofweek.astype(int)
    Xf = pd.get_dummies(f[["t", "dow"]], columns=["dow"], drop_first=False)
    for c in X.columns:
        if c not in Xf.columns:
            Xf[c] = 0
    Xf = Xf[X.columns]
    f["yhat"] = model.predict(Xf.to_numpy())
    f["yhat"] = f["yhat"].clip(lower=0.0)
    return f[["day", "yhat"]]

@st.cache_data(ttl=60)
def _inactive_customers_last_nd(n_days: int = 30) -> dict[str, float]:
    """
    Churn-like KPI:
    Customers who have ordered before, but have NOT ordered in the last N days
    (relative to the latest order date in the dataset).
    """
    n_days = int(max(1, min(int(n_days), 365)))
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            WITH asof AS (
              SELECT MAX(order_date) AS as_of
              FROM public.orders
            ),
            per AS (
              SELECT customer_id, MAX(order_date) AS last_order
              FROM public.orders
              GROUP BY customer_id
            ),
            calc AS (
              SELECT p.customer_id, p.last_order, a.as_of
              FROM per p
              CROSS JOIN asof a
            )
            SELECT
              COALESCE(SUM(CASE WHEN last_order < as_of - INTERVAL '{n_days} days' THEN 1 ELSE 0 END), 0) AS inactive,
              COALESCE(SUM(CASE WHEN last_order >= as_of - INTERVAL '{n_days} days' THEN 1 ELSE 0 END), 0) AS active,
              COALESCE(COUNT(*), 0) AS customers_with_orders
            FROM calc
            """
        )
        inactive, active, total = cur.fetchone()
        inactive = float(inactive or 0)
        active = float(active or 0)
        total = float(total or 0)
        return {"inactive": inactive, "active": active, "total": total}
    finally:
        cur.close()


@st.cache_data(ttl=60)
def _units_sold_total() -> int:
    conn = _get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(SUM(quantity), 0) AS units FROM public.order_items")
        return int(cur.fetchone()[0] or 0)
    finally:
        cur.close()


def _render_grid(df: pd.DataFrame, height: int = 420) -> None:
    if AgGrid is not None and GridOptionsBuilder is not None:
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_default_column(filter=True, sortable=True, resizable=True)
        AgGrid(df, gridOptions=gb.build(), theme="streamlit", height=height)
    else:
        st.dataframe(df, width="stretch", height=height)


def _roles_value_section() -> None:
    st.markdown("### Who uses this dashboard (and why)")
    rows = [
        ("Business Manager", "Sales & revenue decisions"),
        ("Marketing Analyst", "Customer insights (segments, retention, LTV)"),
        ("Product Manager", "Product optimization (top products, also-bought)"),
        ("Data Analyst", "Deeper reporting + anomaly investigation"),
        ("Management", "Strategic planning (forecast + risks)"),
    ]
    df = pd.DataFrame(rows, columns=["Role", "What they decide with it"])
    st.dataframe(df, width="stretch", height=220)


def _how_it_works() -> None:
    st.markdown(
        """
**Data sources (Firebolt tables)**
- `public.orders`: `order_date`, `total_amount` → revenue trends + forecasting
- `public.order_items` + `public.products`: product performance + “also bought” recommendations
- `public.page_views`: traffic + conversion KPIs + monitoring

**What each page is for**
- **Overview**: quick health check (KPIs + monthly revenue + users sample)
- **Analytics**: descriptive analytics (what happened, where, which products/pages)
- **Decision Assistant**: predictive/prescriptive (what may happen next + what action to take)

**How key metrics are computed (simple + explainable)**
- **Revenue**: `SUM(orders.total_amount)`
- **Orders**: `COUNT(*)` from `orders`
- **Conversion rate (proxy)**: `orders / COUNT(DISTINCT page_views.session_id)`
- **AOV**: `revenue / orders`
- **Segmentation (RFM)**: per customer → `recency_days`, `frequency`, `monetary` (lookback window)
        """
    )


def _forecast_next_days(daily_df: pd.DataFrame, horizon_days: int = 30) -> pd.DataFrame:
    """
    Simple practical forecast: Ridge regression with trend + day-of-week.
    Returns df with columns: day, yhat
    """
    if np is None or Ridge is None:
        return pd.DataFrame()
    if daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df = df.sort_values("day")
    df["t"] = (df["day"] - df["day"].min()).dt.days.astype(int)
    df["dow"] = df["day"].dt.dayofweek.astype(int)
    X = pd.get_dummies(df[["t", "dow"]], columns=["dow"], drop_first=False)
    y = df["revenue"].astype(float).fillna(0.0).to_numpy()

    model = Ridge(alpha=1.0)
    model.fit(X.to_numpy(), y)

    future_days = pd.date_range(df["day"].max() + pd.Timedelta(days=1), periods=int(horizon_days), freq="D")
    f = pd.DataFrame({"day": future_days})
    f["t"] = (f["day"] - df["day"].min()).dt.days.astype(int)
    f["dow"] = f["day"].dt.dayofweek.astype(int)
    Xf = pd.get_dummies(f[["t", "dow"]], columns=["dow"], drop_first=False)
    # align columns
    for c in X.columns:
        if c not in Xf.columns:
            Xf[c] = 0
    Xf = Xf[X.columns]

    f["yhat"] = model.predict(Xf.to_numpy())
    f["yhat"] = f["yhat"].clip(lower=0.0)
    return f[["day", "yhat"]]


def _detect_anomalies(daily_df: pd.DataFrame) -> pd.DataFrame:
    if np is None or IsolationForest is None:
        return pd.DataFrame()
    if daily_df.empty:
        return pd.DataFrame()

    df = daily_df.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df = df.sort_values("day")
    vals = df[["revenue"]].astype(float).fillna(0.0).to_numpy()
    clf = IsolationForest(n_estimators=200, contamination=0.06, random_state=42)
    pred = clf.fit_predict(vals)
    df["is_anomaly"] = pred == -1
    return df


def _segment_customers(rfm_df: pd.DataFrame, k: int = 3) -> pd.DataFrame:
    if np is None or KMeans is None:
        return pd.DataFrame()
    if rfm_df.empty:
        return pd.DataFrame()

    df = rfm_df.copy()
    # Basic cleanup
    for col in ["recency_days", "frequency", "monetary"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # scale-ish without extra deps: log transform for frequency/monetary
    X = pd.DataFrame(
        {
            "recency": df["recency_days"].astype(float),
            "frequency": np.log1p(df["frequency"].astype(float)),
            "monetary": np.log1p(df["monetary"].astype(float)),
        }
    )

    km = KMeans(n_clusters=int(k), n_init=10, random_state=42)
    df["cluster"] = km.fit_predict(X.to_numpy())

    # name clusters by average monetary (highest => High value)
    means = df.groupby("cluster")["monetary"].mean().sort_values(ascending=False)
    order = list(means.index)
    names = {}
    if len(order) >= 1:
        names[order[0]] = "High value"
    if len(order) >= 2:
        names[order[1]] = "Occasional"
    for c in order[2:]:
        names[c] = "One-time / Low value"
    df["segment"] = df["cluster"].map(names).fillna("Segment")
    return df


def _also_bought(items_df: pd.DataFrame, product_id: int, top_n: int = 10) -> pd.DataFrame:
    if items_df.empty:
        return pd.DataFrame()
    df = items_df[["order_id", "product_id"]].copy()
    df["order_id"] = pd.to_numeric(df["order_id"], errors="coerce")
    df["product_id"] = pd.to_numeric(df["product_id"], errors="coerce")
    df = df.dropna()
    df["order_id"] = df["order_id"].astype(int)
    df["product_id"] = df["product_id"].astype(int)

    orders_with_x = set(df.loc[df["product_id"] == int(product_id), "order_id"].unique().tolist())
    if not orders_with_x:
        return pd.DataFrame(columns=["product_id", "co_buys"])

    co = df[df["order_id"].isin(orders_with_x)]
    co = co[co["product_id"] != int(product_id)]
    out = co.groupby("product_id", as_index=False).size().rename(columns={"size": "co_buys"})
    out = out.sort_values("co_buys", ascending=False).head(int(top_n))
    return out


monthly_rev = _monthly_revenue(ts)
last_month_rev = float(monthly_rev["revenue"].iloc[-1]) if not monthly_rev.empty else 0.0

with st.sidebar:
    st.subheader("Connection")
    try:
        s = get_firebolt_settings()
        st.caption(f"Database: `{s.get('database')}`")
        st.caption(f"Engine: `{s.get('engine_name')}`")
        st.caption(f"Account: `{s.get('account_name')}`")
        if st.button("Test Firebolt connection", key="test_firebolt_conn"):
            try:
                conn = _get_conn()
                cur = conn.cursor()
                cur.execute("SELECT 1")
                _ = cur.fetchone()
                cur.close()
                st.success("Firebolt connection OK.")
            except Exception as e:
                st.error("Firebolt connection failed.")
                st.code(repr(e))
        if st.button("Refresh data"):
            _load_all.clear()
            _load_rfm.clear()
            _load_reco_inputs.clear()
            st.rerun()
    except Exception as e:
        st.error(str(e))
        st.stop()

    st.divider()
    nav = ["Overview", "Analytics", "Decision Assistant"]
    if role in ["Admin", "Analyst"]:
        nav.append("Data Pipeline")
    if role == "Admin":
        nav.append("User Management")
    nav.extend(["Monitoring", "Settings"])
    page = st.radio("Go to", nav, index=0)


if page == "Overview":
    with st.expander("How to use this dashboard", expanded=False):
        _roles_value_section()
        st.divider()
        _how_it_works()

    st.caption(
        f"**Revenue** = SUM(`orders.total_amount`) · "
        f"**Orders** = COUNT(*) from `orders` · "
        f"**Units sold** = SUM(`order_items.quantity`)"
    )

    w30 = _last_nd_window(ts, 30)
    units30 = _units_sold_last_nd(30)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Revenue (last 30d)", f"{CURRENCY_SYMBOL}{w30['revenue']:,.0f}")
    k2.metric("Orders (last 30d)", f"{int(w30['orders']):,}")
    k3.metric("Units sold (last 30d)", f"{units30:,}")
    k4.metric("Repeat Rate", f"{biz.repeat_rate*100:.1f}%")

    st.subheader("Quick Insights")
    ins = _last_7d_insights(ts)
    rev_7d = ins["rev_7d"]
    rev_prev = ins["rev_prev_7d"]
    ord_7d = ins["orders_7d"]
    ord_prev = ins["orders_prev_7d"]
    rev_delta = ((rev_7d - rev_prev) / rev_prev) if rev_prev > 0 else 0.0
    ord_delta = ((ord_7d - ord_prev) / ord_prev) if ord_prev > 0 else 0.0
    churn = _inactive_customers_last_nd(30)
    inactive30 = int(churn["inactive"])
    active30 = int(churn["active"])
    total_ord_customers = int(churn["total"])
    inactive_rate = _clamp01((inactive30 / total_ord_customers) if total_ord_customers > 0 else 0.0)

    i1, i2, i3, i4 = st.columns(4)
    i1.metric(
        "Revenue (last 7d)",
        f"{CURRENCY_SYMBOL}{rev_7d:,.0f}",
        f"{rev_delta:+.0%}" if rev_prev > 0 else "—",
    )
    i2.metric("Orders (last 7d)", f"{int(ord_7d):,}", f"{ord_delta:+.0%}" if ord_prev > 0 else "—")
    i3.metric("Avg order value (AOV)", f"{CURRENCY_SYMBOL}{biz.avg_order_value:,.2f}", "from orders")
    i4.metric("Inactive customers (30d)", f"{inactive30:,}", f"{inactive_rate:.0%}" if total_ord_customers > 0 else "—")
    st.caption("These insights use the latest 7 days present in your dataset (not the current calendar week).")
    st.caption(
        "Inactive customers (30d) means: customers who ordered before, but did not place any order in the last 30 days "
        "(relative to the latest order date in your data)."
    )

    st.subheader("Monthly Revenue")
    st.caption("Purpose: track growth/seasonality. Source: `public.orders` → monthly SUM(revenue).")
    if monthly_rev.empty:
        st.info("No revenue data found.")
    else:
        chart_df = monthly_rev.copy()
        chart_df["Month"] = pd.to_datetime(chart_df["month"]).dt.strftime("%b %Y")
        chart_df["Revenue"] = chart_df["revenue"]
        if px is None:
            st.line_chart(chart_df.set_index("Month")["Revenue"])
        else:
            fig = px.line(chart_df, x="Month", y="Revenue", markers=True, title="Monthly Revenue")
            st.plotly_chart(fig, use_container_width=True)

    st.write("### 👥 Users")
    st.caption("Purpose: quick customer snapshot. Source: `public.customers` (sample rows).")
    _render_grid(customers, height=420)

    st.write("### Top Highlights")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Top products (by sales)**")
        if top_products.empty:
            st.info("No product sales data yet.")
        else:
            st.dataframe(top_products[["product_name", "sales", "units_sold"]].head(5), width="stretch", height=220)
    with c2:
        st.write("**Top pages (by views)**")
        if top_pages.empty:
            st.info("No page view data yet.")
        else:
            st.dataframe(top_pages[["page_url", "views"]].head(5), width="stretch", height=220)

    csv = monthly_rev.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Revenue Data", data=csv, file_name="revenue.csv", mime="text/csv")

elif page == "Analytics":
    st.subheader("Orders & Revenue by Day")
    st.caption("Purpose: identify daily demand changes and revenue trend. Source: `public.orders` grouped by day.")
    if ts.empty:
        st.info("No orders found.")
    else:
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

        c1, c2 = st.columns(2)
        c1.altair_chart(orders_chart, width="stretch")
        c2.altair_chart(revenue_chart, width="stretch")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top Products by Sales")
        st.caption("Purpose: identify best sellers for pricing/stock/marketing. Source: `order_items` × `products`.")
        if top_products.empty:
            st.info("No order_items found.")
        else:
            _render_grid(top_products, height=360)
    with c2:
        st.subheader("Top Pages")
        st.caption("Purpose: see which pages drive traffic (content/SEO). Source: `public.page_views` grouped by URL.")
        top_limit = st.slider("Top pages limit", min_value=5, max_value=50, value=10, step=5)
        if top_limit != 10:
            conn = _get_conn()
            cur = conn.cursor()
            try:
                top_pages_df = get_top_pages(cur, limit=int(top_limit))
            finally:
                cur.close()
        else:
            top_pages_df = top_pages

        if top_pages_df.empty:
            st.info("No page URLs to show yet.")
        else:
            _render_grid(top_pages_df, height=300)

    show_sample = st.checkbox("Show latest page view events (sample)", value=True)
    if show_sample:
        st.subheader("Latest page view events")
        st.caption("Purpose: investigate recent traffic sessions. Source: latest rows from `public.page_views`.")
        if page_views_sample.empty:
            st.info("No events found.")
        else:
            _render_grid(page_views_sample, height=360)

elif page == "Decision Assistant":
    st.subheader("Decision Assistant (Predictive + Insights)")
    st.caption("Forecasting • Segmentation • Anomaly detection • Recommendations • Predictive alerts")

    with st.expander("Who this helps", expanded=True):
        _roles_value_section()
        st.divider()
        _how_it_works()

    # Build a daily series from existing ts
    daily = ts.copy()
    if not daily.empty:
        daily["day"] = pd.to_datetime(daily["day"]).dt.normalize()
        daily = daily.sort_values("day")
    else:
        st.warning("No order history available yet. Load data in Data Pipeline first.")

    st.markdown("### Forecasting (Next 7/30 days)")
    if np is None or Ridge is None:
        st.info("Install ML deps to enable forecasting: `numpy`, `scikit-learn`.")
    elif daily.empty:
        st.info("No orders to forecast yet.")
    else:
        horizon = st.selectbox("Forecast horizon", [7, 30], index=1)
        # Forecast revenue and orders; estimate units sold using recent units/order ratio.
        fc_rev = _forecast_series_next_days(daily, y_col="revenue", horizon_days=int(horizon))
        fc_ord = _forecast_series_next_days(daily, y_col="orders", horizon_days=int(horizon))

        units30 = float(_units_sold_last_nd(30))
        ord30 = float(_last_nd_window(ts, 30)["orders"])
        units_per_order = (units30 / ord30) if ord30 > 0 else 0.0
        fc_units = fc_ord.copy()
        if not fc_units.empty:
            fc_units["yhat"] = (fc_units["yhat"].astype(float) * units_per_order).clip(lower=0.0)

        def _plot(actual_col: str, fc_df: pd.DataFrame, label: str) -> None:
            if fc_df.empty:
                st.info("Not enough data to forecast.")
                return
            actual = daily[["day", actual_col]].rename(columns={actual_col: "value"}).assign(series="Actual")
            forecast = fc_df.rename(columns={"yhat": "value"}).assign(series="Forecast")
            plot_df = pd.concat([actual, forecast], ignore_index=True)
            if px is None:
                st.line_chart(plot_df.pivot(index="day", columns="series", values="value"))
            else:
                fig = px.line(plot_df, x="day", y="value", color="series", markers=True, title=label)
                st.plotly_chart(fig, use_container_width=True)

        tab_rev, tab_ord, tab_units = st.tabs(["Revenue", "Orders", "Units sold (est.)"])
        with tab_rev:
            _plot("revenue", fc_rev, "Revenue forecast")
        with tab_ord:
            _plot("orders", fc_ord, "Orders forecast")
        with tab_units:
            if fc_units.empty:
                st.info("Not enough data to estimate units sold.")
            else:
                if px is None:
                    st.line_chart(fc_units.set_index("day")["yhat"])
                else:
                    fig = px.line(fc_units, x="day", y="yhat", markers=True, title="Units sold forecast (estimated)")
                    st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Units sold is estimated using last-30d ratio: {units_per_order:.2f} units/order.")

        st.divider()
        s1, s2, s3 = st.columns(3)
        if not fc_rev.empty:
            s1.metric("Expected revenue (sum)", f"{CURRENCY_SYMBOL}{fc_rev['yhat'].sum():,.0f}")
        if not fc_ord.empty:
            s2.metric("Expected orders (sum)", f"{int(round(fc_ord['yhat'].sum())):,}")
        if not fc_units.empty:
            s3.metric("Expected units sold (sum)", f"{int(round(fc_units['yhat'].sum())):,}")

        with st.expander("Forecast table", expanded=False):
            out = pd.DataFrame(
                {
                    "day": fc_rev["day"].dt.strftime("%Y-%m-%d") if not fc_rev.empty else [],
                    "revenue_pred": fc_rev["yhat"] if not fc_rev.empty else [],
                    "orders_pred": fc_ord["yhat"] if not fc_ord.empty else [],
                    "units_pred": fc_units["yhat"] if not fc_units.empty else [],
                }
            )
            if not out.empty:
                out2 = out.copy()
                if "revenue_pred" in out2.columns:
                    out2["revenue_pred"] = out2["revenue_pred"].fillna(0).map(lambda v: _fmt_money0(float(v)))
                if "orders_pred" in out2.columns:
                    out2["orders_pred"] = out2["orders_pred"].fillna(0).map(lambda v: f"{int(round(float(v))):,}")
                if "units_pred" in out2.columns:
                    out2["units_pred"] = out2["units_pred"].fillna(0).map(lambda v: f"{int(round(float(v))):,}")
                st.dataframe(out2, width="stretch", height=320)
            else:
                st.info("No forecast rows to show.")

    st.markdown("### Customer Segmentation (Clustering)")
    if np is None or KMeans is None:
        st.info("Install ML deps to enable segmentation: `numpy`, `scikit-learn`.")
    else:
        lookback = st.slider("Lookback window (days)", 30, 365, 180, step=30)
        k = st.slider("Number of segments (k)", 3, 6, 3)
        rfm = _load_rfm(lookback_days=int(lookback), limit=5000)
        if rfm.empty:
            st.info("No RFM data available yet.")
        else:
            seg = _segment_customers(rfm, k=int(k))
            if seg.empty:
                st.info("Segmentation not available.")
            else:
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.write("Segment counts")
                    st.dataframe(seg["segment"].value_counts().rename_axis("segment").reset_index(name="customers"))
                with c2:
                    st.write("Sample customers with segments")
                    _render_grid(
                        seg[["customer_id", "recency_days", "frequency", "monetary", "segment"]].head(200),
                        height=360,
                    )

    st.markdown("### Anomaly Detection (Sales spike/drop)")
    if np is None or IsolationForest is None:
        st.info("Install ML deps to enable anomaly detection: `numpy`, `scikit-learn`.")
    elif daily.empty:
        st.info("No daily revenue data yet.")
    else:
        an = _detect_anomalies(daily)
        if an.empty:
            st.info("No anomalies computed.")
        else:
            anomalies = an[an["is_anomaly"]].copy()
            c1, c2 = st.columns([2, 1])
            with c1:
                plot_df = an.copy()
                plot_df["series"] = plot_df["is_anomaly"].map({True: "Anomaly", False: "Normal"})
                if px is None:
                    st.line_chart(plot_df.set_index("day")["revenue"])
                else:
                    fig = px.scatter(plot_df, x="day", y="revenue", color="series", title="Daily revenue anomalies")
                    st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.metric("Anomaly days", int(anomalies.shape[0]))
                if not anomalies.empty:
                    st.dataframe(anomalies[["day", "revenue"]].tail(20), width="stretch", height=260)

    st.markdown("### Product Recommendation (Also bought)")
    items_df, products_df = _load_reco_inputs(lookback_days=180, limit=200_000)
    if items_df.empty or products_df.empty:
        st.info("Recommendation inputs not available yet.")
    else:
        # pick from top products list (already loaded)
        prod_map = products_df.copy()
        prod_map["label"] = prod_map["product_name"].astype(str) + " (#" + prod_map["product_id"].astype(str) + ")"
        options = prod_map.sort_values("product_name")["label"].tolist()
        default_label = options[0] if options else None
        chosen = st.selectbox("Choose a product", options=options, index=0 if default_label else 0)
        pid = int(chosen.split("(#")[-1].replace(")", "").strip())
        rec = _also_bought(items_df, product_id=pid, top_n=10)
        if rec.empty:
            st.info("Not enough co-purchase data for this product.")
        else:
            rec = rec.merge(products_df, on="product_id", how="left")
            rec = rec[["product_id", "product_name", "category", "co_buys"]].sort_values("co_buys", ascending=False)
            _render_grid(rec, height=300)

    st.markdown("### Location & Category Growth (Marketing)")
    st.caption("Helps marketers decide budget by city/location and by product category.")

    lookback_loc = st.selectbox("Lookback window for growth (days)", [30, 60, 90, 180, 365], index=2, key="mk_lb")
    horizon_loc = st.selectbox("Forecast horizon (days)", [7, 30], index=1, key="mk_hz")

    city_ts = _load_city_ts(limit_days=int(lookback_loc))
    if city_ts.empty or "city" not in city_ts.columns:
        st.info(
            "City data not available yet. "
            "If you just upgraded: re-upload & auto-load `sample_upload_template_realistic_v2.xlsx` "
            "so `orders.city` / `orders.country` get populated."
        )
    else:
        city_ts["day"] = pd.to_datetime(city_ts["day"]).dt.normalize()
        # Growth: last 7d vs prev 7d per city
        end = city_ts["day"].max()
        w7_start = end - pd.Timedelta(days=6)
        wprev_start = w7_start - pd.Timedelta(days=7)
        wprev_end = w7_start - pd.Timedelta(days=1)

        g7 = city_ts[(city_ts["day"] >= w7_start) & (city_ts["day"] <= end)].groupby("city")["orders"].sum()
        gp = city_ts[(city_ts["day"] >= wprev_start) & (city_ts["day"] <= wprev_end)].groupby("city")["orders"].sum()
        total7 = float(g7.sum() or 0.0)
        min_prev_for_pct = st.slider("Min prev-7d orders for % growth", 1, 20, 5, key="mk_city_min_prev")
        growth = pd.DataFrame({"orders_7d": g7, "orders_prev_7d": gp}).fillna(0).reset_index()
        growth["share_7d"] = growth["orders_7d"].apply(lambda v: (float(v) / total7) if total7 > 0 else 0.0)
        growth["delta_orders"] = growth["orders_7d"] - growth["orders_prev_7d"]
        growth["growth_pct"] = growth.apply(
            lambda r: _pct_change(r["orders_7d"], r["orders_prev_7d"]) if float(r["orders_prev_7d"]) >= min_prev_for_pct else None,
            axis=1,
        )
        growth = growth.sort_values("orders_7d", ascending=False)

        c1, c2 = st.columns([1, 2])
        with c1:
            st.write("**Top cities (orders)**")
            gshow = growth[["city", "orders_7d", "share_7d", "delta_orders", "growth_pct"]].head(10).copy()
            gshow["orders_7d"] = gshow["orders_7d"].fillna(0).map(lambda v: f"{int(round(float(v))):,}")
            gshow["share_7d"] = gshow["share_7d"].fillna(0).map(lambda v: _fmt_pct(float(v), 0))
            gshow["delta_orders"] = gshow["delta_orders"].fillna(0).map(lambda v: f"{int(round(float(v))):+d}")
            gshow["growth_pct"] = gshow["growth_pct"].map(lambda v: "—" if v is None else _fmt_pct(float(v), 0))
            st.dataframe(gshow, width="stretch", height=320)

        with c2:
            # Choose a city and forecast orders for that city
            cities = [c for c in growth["city"].tolist() if c and c != "Unknown"]
            city_choice = st.selectbox("City to forecast", cities if cities else growth["city"].tolist(), key="mk_city")
            city_daily = city_ts[city_ts["city"] == city_choice][["day", "orders", "revenue"]].copy()
            city_daily = city_daily.sort_values("day")
            fc_city_orders = _forecast_series_next_days(city_daily, y_col="orders", horizon_days=int(horizon_loc))

            if fc_city_orders.empty:
                st.info("Not enough city history to forecast.")
            else:
                plot_df = pd.concat(
                    [
                        city_daily[["day", "orders"]].rename(columns={"orders": "value"}).assign(series="Actual"),
                        fc_city_orders.rename(columns={"yhat": "value"}).assign(series="Forecast"),
                    ],
                    ignore_index=True,
                )
                if px is None:
                    st.line_chart(plot_df.pivot(index="day", columns="series", values="value"))
                else:
                    fig = px.line(
                        plot_df,
                        x="day",
                        y="value",
                        color="series",
                        markers=True,
                        title=f"Expected orders in {city_choice} (next {horizon_loc} days)",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                st.metric("Expected orders (sum)", f"{int(round(fc_city_orders['yhat'].sum())):,}")

    cat_ts = _load_category_ts(limit_days=int(lookback_loc))
    if not cat_ts.empty:
        cat_ts["day"] = pd.to_datetime(cat_ts["day"]).dt.normalize()
        end = cat_ts["day"].max()
        w7_start = end - pd.Timedelta(days=6)
        wprev_start = w7_start - pd.Timedelta(days=7)
        wprev_end = w7_start - pd.Timedelta(days=1)
        g7 = cat_ts[(cat_ts["day"] >= w7_start) & (cat_ts["day"] <= end)].groupby("category")["revenue"].sum()
        gp = cat_ts[(cat_ts["day"] >= wprev_start) & (cat_ts["day"] <= wprev_end)].groupby("category")["revenue"].sum()
        total_rev7 = float(g7.sum() or 0.0)
        min_prev_cat = st.slider("Min prev-7d revenue for % growth", 0, 5000, 200, step=50, key="mk_cat_min_prev")
        cg = pd.DataFrame({"rev_7d": g7, "rev_prev_7d": gp}).fillna(0).reset_index()
        cg["share_7d"] = cg["rev_7d"].apply(lambda v: (float(v) / total_rev7) if total_rev7 > 0 else 0.0)
        cg["delta_rev"] = cg["rev_7d"] - cg["rev_prev_7d"]
        cg["growth_pct"] = cg.apply(
            lambda r: _pct_change(r["rev_7d"], r["rev_prev_7d"])
            if float(r["rev_prev_7d"]) >= float(min_prev_cat)
            else None,
            axis=1,
        )
        cg = cg.sort_values("rev_7d", ascending=False)
        st.write("**Category growth (revenue last 7d vs prev 7d)**")
        cshow = cg[["category", "rev_7d", "share_7d", "delta_rev", "rev_prev_7d", "growth_pct"]].head(10).copy()
        def _fmt_delta_money(v: float) -> str:
            try:
                v = float(v or 0.0)
            except Exception:
                return ""
            if v == 0:
                return f"{CURRENCY_SYMBOL}0"
            sign = "+" if v > 0 else "-"
            return f"{sign}{CURRENCY_SYMBOL}{abs(v):,.0f}"

        cshow["delta_rev"] = cshow["delta_rev"].fillna(0).map(_fmt_delta_money)

        # Show NEW if prev was 0 but current > 0; otherwise show signed %.
        def _fmt_growth_row(prev: float, curr: float, v) -> str:
            prev = float(prev or 0.0)
            curr = float(curr or 0.0)
            if prev <= 0 and curr > 0:
                return "NEW"
            return "—" if v is None else _fmt_pct_signed(float(v), 0)

        cshow["growth_pct"] = cshow.apply(
            lambda r: _fmt_growth_row(r["rev_prev_7d"], r["rev_7d"], r["growth_pct"]),
            axis=1,
        )

        # Format after computing growth strings (avoid float conversion issues)
        cshow["rev_7d"] = cshow["rev_7d"].fillna(0).map(lambda v: _fmt_money0(float(v)))
        cshow["share_7d"] = cshow["share_7d"].fillna(0).map(lambda v: _fmt_pct(float(v), 0))
        cshow = cshow.drop(columns=["rev_prev_7d"])
        st.dataframe(cshow, width="stretch", height=280)

    st.markdown("### Intelligent KPI Alerts (Analytics + AI)")
    st.caption("Actionable alerts generated from forecast + anomaly + trend signals.")
    if daily.empty:
        st.info("No alerts yet (no order history).")
    else:
        # Local lightweight Alert struct (also compatible with monitoring.alerts.Alert)
        class _UIAlert(dict):
            pass

        ui_alerts: list[_UIAlert] = []

        def _add(sev: str, metric: str, msg: str, value: float | int | None = None) -> None:
            ui_alerts.append(_UIAlert(severity=sev, metric=metric, message=msg, value=value))

        # 1) Forecast-based alert (next 7d vs last 7d)
        if np is not None and Ridge is not None:
            fc7 = _forecast_next_days(daily, horizon_days=7)
            if not fc7.empty:
                last7 = float(daily.tail(7)["revenue"].sum())
                next7 = float(fc7["yhat"].sum())
                if last7 > 0:
                    change = (next7 - last7) / last7
                    if change <= -0.35:
                        _add("CRITICAL", "forecast_revenue_7d", f"Revenue likely to drop {change:.0%} next 7 days", next7)
                    elif change <= -0.20:
                        _add("WARN", "forecast_revenue_7d", f"Revenue likely to drop {change:.0%} next 7 days", next7)
                    elif change >= 0.30:
                        _add("INFO", "forecast_revenue_7d", f"Revenue likely to grow {change:.0%} next 7 days", next7)

        # 2) Latest-day anomaly + simple rolling z-score confirmation
        if np is not None and IsolationForest is not None:
            an = _detect_anomalies(daily)
            if not an.empty:
                latest = an.tail(1).iloc[0]
                if bool(latest.get("is_anomaly", False)):
                    _add("WARN", "revenue_anomaly", "Latest day looks anomalous vs history (spike/drop).", float(latest["revenue"]))

        # Rolling z-score (works even without IsolationForest)
        try:
            z_df = daily.copy()
            z_df["day"] = pd.to_datetime(z_df["day"]).dt.normalize()
            z_df = z_df.sort_values("day")
            z_df["rev"] = pd.to_numeric(z_df["revenue"], errors="coerce").fillna(0.0)
            if len(z_df) >= 14:
                roll = z_df["rev"].rolling(window=30, min_periods=14)
                mu = roll.mean()
                sd = roll.std(ddof=0).replace(0, pd.NA)
                z = (z_df["rev"] - mu) / sd
                z_last = float(z.tail(1).iloc[0]) if not pd.isna(z.tail(1).iloc[0]) else 0.0
                rev_last = float(z_df["rev"].tail(1).iloc[0])
                if z_last <= -2.5:
                    _add("CRITICAL", "revenue_zscore", f"Revenue unusually low today (z={z_last:.1f}).", rev_last)
                elif z_last <= -2.0:
                    _add("WARN", "revenue_zscore", f"Revenue below normal range today (z={z_last:.1f}).", rev_last)
                elif z_last >= 3.0:
                    _add("INFO", "revenue_zscore", f"Revenue unusually high today (z={z_last:.1f}).", rev_last)
        except Exception:
            pass

        # 3) Product demand rising / stock recommendation (last 7d vs prev 7d)
        # Goal: show actionable "which products, how many units to keep available".
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                """
                WITH asof AS (
                  SELECT MAX(order_date) AS as_of
                  FROM public.orders
                ),
                w AS (
                  SELECT
                    oi.product_id,
                    SUM(CASE WHEN o.order_date >= DATEADD('day', -7, a.as_of) THEN oi.quantity ELSE 0 END) AS q_7d,
                    SUM(CASE WHEN o.order_date >= DATEADD('day', -14, a.as_of)
                              AND o.order_date < DATEADD('day', -7, a.as_of) THEN oi.quantity ELSE 0 END) AS q_prev_7d
                  FROM public.order_items oi
                  JOIN public.orders o ON o.order_id = oi.order_id
                  CROSS JOIN asof a
                  GROUP BY 1
                )
                SELECT w.product_id, w.q_7d, w.q_prev_7d, p.product_name
                FROM w
                JOIN public.products p ON p.product_id = w.product_id
                ORDER BY (w.q_7d - w.q_prev_7d) DESC
                LIMIT 20
                """
            )
            rows = cur.fetchall()
            cur.close()

            # Filter out products with zero sales in the last week, then take top 5 movers.
            movers = [(pid, q7, qprev, pname) for (pid, q7, qprev, pname) in (rows or []) if float(q7 or 0) > 0]
            movers = movers[:5]

            if movers:
                rising_msgs: list[str] = []
                stock_msgs: list[str] = []
                recommended_msgs: list[str] = []

                # How many days of inventory we want to keep available (heuristic).
                target_days = 14
                for pid, q7, qprev, pname in movers:
                    q7 = float(q7 or 0)
                    qprev = float(qprev or 0)
                    ch = _pct_change(q7, qprev)

                    # Demand rising signal (keep it readable, avoid misleading huge %)
                    if qprev >= 5 and ch is not None and ch >= 0.6:
                        rising_msgs.append(f"{pname} ({_fmt_pct(ch, 0)}, {int(q7)} units)")
                    elif qprev < 5 and q7 >= 10:
                        rising_msgs.append(f"{pname} (+{int(q7 - qprev)} units, {int(q7)} units)")

                    # Recommended availability: 2 weeks of avg daily demand, with a small uplift if growing.
                    avg_daily = q7 / 7.0
                    uplift = 1.25 if (ch is not None and ch >= 0.4) else 1.0
                    rec_units = int(max(1, round(avg_daily * target_days * uplift)))
                    recommended_msgs.append(f"{pname}: keep ~{rec_units} units available (sold {int(q7)} in 7d)")

                    # Heuristic "stock risk": high volume + strong rise (no stock table available).
                    if q7 >= 30 and ((qprev > 0 and (q7 - qprev) / qprev >= 0.5) or (qprev == 0 and q7 >= 40)):
                        stock_msgs.append(f"{pname} ({int(q7)} units in 7d)")

                if rising_msgs:
                    _add("INFO", "product_demand", "Demand rising: " + ", ".join(rising_msgs))
                if recommended_msgs:
                    _add("INFO", "recommended_availability", "Suggested availability: " + "; ".join(recommended_msgs))
                if stock_msgs:
                    _add("WARN", "stock_risk", "Potential stock risk (demand spike): " + ", ".join(stock_msgs))
        except Exception as e:
            # Don't break the dashboard; but make it debuggable for Admins.
            try:
                if role == "Admin":
                    st.caption(f"(Debug) Product-demand alert generation failed: {e}")
            except Exception:
                pass

        if not ui_alerts:
            st.success("No alerts triggered right now.")
        else:
            # Table (compact) + full readable messages (wrapped) below
            df_alerts = pd.DataFrame(ui_alerts)
            df_show = df_alerts[["severity", "metric", "value"]].copy()
            if "value" in df_show.columns:
                def _fmt_val(v):
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        return ""
                    try:
                        # Most values are revenue/units; show as integer for readability.
                        return f"{float(v):,.0f}"
                    except Exception:
                        return str(v)
                df_show["value"] = df_show["value"].map(_fmt_val)
            st.dataframe(df_show, width="stretch", height=220)

            st.markdown("#### Alert details")
            for i, a in enumerate(ui_alerts, start=1):
                sev = str(a.get("severity", "INFO"))
                metric = str(a.get("metric", "metric"))
                msg = str(a.get("message", ""))
                val = a.get("value")

                title = f"{sev} · {metric}"
                with st.expander(title, expanded=(i == 1)):
                    st.markdown(msg)
                    if val is not None:
                        st.caption(f"Value: `{val}`")

            # Optional: persist into Firebolt alerts table so Monitoring can show it.
            if st.button("Save these alerts to Monitoring", key="save_pred_alerts"):
                try:
                    from monitoring.alerts import Alert as FBAlert, ensure_alerts_table, write_alert

                    conn = _get_conn()
                    cur = conn.cursor()
                    try:
                        ensure_alerts_table(cur)
                        for a in ui_alerts:
                            write_alert(
                                cur,
                                FBAlert(
                                    severity=str(a.get("severity")),
                                    metric=str(a.get("metric")),
                                    message=str(a.get("message")),
                                    value=a.get("value"),
                                ),
                            )
                        st.success(f"Saved {len(ui_alerts)} alerts into public.alerts")
                    finally:
                        cur.close()
                except Exception as e:
                    st.error("Failed to save alerts.")
                    st.code(str(e))

elif page == "Data Pipeline":
    if role not in ["Admin", "Analyst"]:
        st.error("You do not have access to Data Pipeline.")
        st.stop()

    st.subheader("Data Pipeline (Generate / Upload → Load to Firebolt)")
    st.caption(
        "Create or upload datasets, validate, load into Firebolt, then explore instantly in the dashboard."
    )

    dataset_dir = Path(ensure_dataset_dir(str(PROJECT_ROOT / "dataset")))

    cgen, cupload = st.columns(2)

    with cgen:
        st.markdown("**Generate dataset (CSV)**")
        st.caption("Use a preset first (small/standard). You can scale up later.")

        preset = st.selectbox(
            "Preset",
            options=["Small (fast)", "Standard", "Large (slow)"],
            index=1,
        )
        if preset == "Small (fast)":
            default_customers, default_products, default_orders, default_events = 200, 50, 500, 2000
        elif preset == "Large (slow)":
            default_customers, default_products, default_orders, default_events = 20000, 2000, 200000, 500000
        else:
            default_customers, default_products, default_orders, default_events = 1000, 200, 5000, 10000

        n_customers = st.number_input(
            "Customers", min_value=1, max_value=1_000_000, value=int(default_customers), step=100
        )
        n_products = st.number_input(
            "Products", min_value=1, max_value=200_000, value=int(default_products), step=10
        )
        n_orders = st.number_input(
            "Orders", min_value=1, max_value=2_000_000, value=int(default_orders), step=1000
        )
        n_events = st.number_input(
            "Page view events", min_value=1, max_value=5_000_000, value=int(default_events), step=1000
        )

        st.markdown("**Optional automation**")
        auto_ensure_tables = st.checkbox("Create tables if missing", value=True, key="gen_auto_ensure_tables")
        auto_load_after_generate = st.checkbox(
            "Auto-load into Firebolt after generating", value=True, key="gen_auto_load_after_generate"
        )
        auto_mode = st.selectbox(
            "Auto-load mode",
            options=["replace", "append"],
            index=0,
            disabled=not auto_load_after_generate,
            key="gen_auto_mode",
        )
        auto_chunk_size = st.number_input(
            "Auto-load chunk size",
            min_value=100,
            max_value=10_000,
            value=5000,
            step=100,
            disabled=not auto_load_after_generate,
            key="gen_auto_chunk_size",
        )
        auto_tables = st.multiselect(
            "Auto-load tables",
            options=list(TABLES.keys()),
            default=list(TABLES.keys()),
            disabled=not auto_load_after_generate,
            help="Loading fewer tables is faster.",
            key="gen_auto_tables",
        )

        if st.button("Generate CSVs into ./dataset", type="primary"):
            customers_path = dataset_dir / "customers.csv"
            products_path = dataset_dir / "products.csv"
            orders_path = dataset_dir / "orders.csv"
            order_items_path = dataset_dir / "order_items.csv"
            page_views_path = dataset_dir / "page_views.csv"

            with st.status("Generating CSVs...", expanded=True) as status:
                try:
                    prog = st.progress(0)
                    st.write("Generating customers...")
                    generate_customers(int(n_customers), str(customers_path))
                    prog.progress(25)

                    st.write("Generating products...")
                    generate_products(int(n_products), str(products_path))
                    prog.progress(50)

                    st.write("Generating orders & order_items...")
                    generate_orders_and_items(
                        int(n_customers),
                        int(n_products),
                        int(n_orders),
                        str(orders_path),
                        str(order_items_path),
                    )
                    prog.progress(80)

                    st.write("Generating page_views...")
                    generate_page_views(int(n_customers), int(n_events), str(page_views_path))
                    prog.progress(100)

                    files = sorted(dataset_dir.glob("*.csv"))
                    summary = []
                    for p in files:
                        mb = p.stat().st_size / (1024 * 1024)
                        summary.append(f"- {p.name} ({mb:.2f} MB)")
                    st.code("\n".join(summary) if summary else "No CSV files found.")

                    status.update(label=f"✅ CSVs generated in: {dataset_dir}", state="complete")

                    # Optionally load straight into Firebolt (end-to-end one-click)
                    if auto_load_after_generate:
                        with st.status("Loading into Firebolt...", expanded=True) as load_status:
                            conn = _get_conn()
                            cur = conn.cursor()
                            try:
                                if auto_ensure_tables:
                                    st.write("Ensuring tables exist...")
                                    create_tables(cur)

                                st.write("Loading CSVs into Firebolt...")
                                tables = list(auto_tables)
                                load_logs: list[str] = []
                                load_prog = st.progress(0)
                                for i, table in enumerate(tables, start=1):
                                    t0 = time.time()
                                    n = load_table(cur, dataset_dir, table, auto_mode, int(auto_chunk_size))
                                    dt = time.time() - t0
                                    load_logs.append(f"✅ {table}: inserted {n:,} ({dt:.1f}s)")
                                    load_prog.progress(int(i / len(tables) * 100))

                                st.code("\n".join(load_logs))
                                load_status.update(label="✅ Loaded into Firebolt", state="complete")
                                _load_all.clear()
                                st.rerun()
                            except Exception as e:
                                load_status.update(label="❌ Load failed", state="error")
                                st.error(str(e))
                            finally:
                                cur.close()
                except Exception as e:
                    status.update(label="❌ CSV generation failed", state="error")
                    st.error(str(e))

    with cupload:
        st.markdown("**Upload dataset (CSV or Excel)**")
        st.caption(
            "Upload either:\n"
            "- One Excel workbook (.xlsx) with sheets named: customers, products, orders, order_items, page_views\n"
            "- OR one or more CSVs named: customers.csv, products.csv, orders.csv, order_items.csv, page_views.csv"
        )

        st.markdown("**Optional: auto-load after upload**")
        auto_load_after_upload = st.checkbox(
            "Auto-load into Firebolt after saving uploads", value=True, key="upload_auto_load_after_upload"
        )
        auto_ensure_tables_upload = st.checkbox(
            "Create tables if missing", value=True, key="upload_auto_ensure_tables"
        )
        auto_mode_upload = st.selectbox(
            "Auto-load mode",
            options=["replace", "append"],
            index=0,
            disabled=not auto_load_after_upload,
            key="upload_auto_mode",
        )
        auto_chunk_size_upload = st.number_input(
            "Auto-load chunk size",
            min_value=100,
            max_value=10_000,
            value=5000,
            step=100,
            disabled=not auto_load_after_upload,
            key="upload_auto_chunk_size",
        )
        auto_tables_upload = st.multiselect(
            "Auto-load tables",
            options=list(TABLES.keys()),
            default=list(TABLES.keys()),
            disabled=not auto_load_after_upload,
            key="upload_auto_tables",
        )

        uploads = st.file_uploader(
            "Choose files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key="upload_files",
        )
        if uploads and st.button("Save uploads into ./dataset"):
            saved: list[str] = []
            errors: list[str] = []

            def _save_csv_bytes(name: str, content: bytes) -> None:
                p = dataset_dir / name
                p.write_bytes(content)
                saved.append(p.name)

            for f in uploads:
                name = (f.name or "").strip()
                if name.lower().endswith(".xlsx"):
                    try:
                        xls = pd.ExcelFile(f)  # type: ignore[arg-type]
                        sheets = {s.lower(): s for s in xls.sheet_names}
                        found_any = False
                        # Optional columns supported by the uploader (older files may not include them)
                        optional_cols = {
                            "products": ["cost"],
                            "orders": ["city", "country"],
                            "order_items": ["purchase_price"],
                        }

                        for table, cols in TABLES.items():
                            sheet_name = sheets.get(table.lower())
                            if not sheet_name:
                                continue
                            found_any = True
                            df = pd.read_excel(xls, sheet_name=sheet_name)
                            required = [c for c in cols if c not in optional_cols.get(table, [])]
                            missing = [c for c in required if c not in df.columns]
                            if missing:
                                errors.append(f"{name}:{sheet_name} missing columns: {missing}")
                                continue
                            for c in optional_cols.get(table, []):
                                if c not in df.columns:
                                    df[c] = None
                            df = df[cols]
                            out_csv = df.to_csv(index=False).encode("utf-8")
                            _save_csv_bytes(f"{table}.csv", out_csv)
                        if not found_any:
                            errors.append(
                                f"{name} has no recognized sheets. Expected sheets: {', '.join(TABLES.keys())}"
                            )
                    except Exception as e:
                        errors.append(f"{name}: {e}")
                else:
                    # CSV: save as-is
                    try:
                        target = dataset_dir / name
                        target.write_bytes(f.getbuffer())
                        saved.append(target.name)
                    except Exception as e:
                        errors.append(f"{name}: {e}")

            if saved:
                st.success(f"Saved: {', '.join(sorted(set(saved)))}")
            if errors:
                st.error("Some files/sheets could not be processed:")
                st.code("\n".join(errors))
            if saved and not errors:
                # Quick sanity checks to avoid confusion (why city/page_views not showing)
                try:
                    if (dataset_dir / "page_views.csv").exists():
                        pv_rows = sum(1 for _ in (dataset_dir / "page_views.csv").open("r", encoding="utf-8")) - 1
                        if pv_rows <= 0:
                            st.warning("page_views.csv has 0 rows. Page views charts will be empty.")
                    if (dataset_dir / "orders.csv").exists():
                        head = pd.read_csv(dataset_dir / "orders.csv", nrows=5)
                        if "city" not in head.columns or "country" not in head.columns:
                            st.warning("orders.csv has no city/country columns. City insights will show as Unknown.")
                        else:
                            # check if values are mostly empty
                            empties = int((head["city"].astype(str).str.strip() == "").sum())
                            if empties >= 4:
                                st.warning("orders.csv city values look empty. City insights may show as Unknown.")
                except Exception:
                    pass

            # Optional: auto-load into Firebolt so the dashboard updates immediately.
            if auto_load_after_upload and saved and not errors:
                selected_tables = [t for t in auto_tables_upload if (dataset_dir / f"{t}.csv").exists()]
                missing_tables = [t for t in auto_tables_upload if not (dataset_dir / f"{t}.csv").exists()]
                if missing_tables:
                    st.warning(f"Skipping missing dataset files: {', '.join(missing_tables)}")

                if selected_tables:
                    with st.status("Loading uploads into Firebolt...", expanded=True) as load_status:
                        conn = _get_conn()
                        cur = conn.cursor()
                        try:
                            if auto_ensure_tables_upload:
                                st.write("Ensuring tables exist...")
                                create_tables(cur)

                            st.write("Loading CSVs into Firebolt...")
                            load_logs: list[str] = []
                            load_prog = st.progress(0)
                            for i, table in enumerate(selected_tables, start=1):
                                t0 = time.time()
                                n = load_table(
                                    cur,
                                    dataset_dir,
                                    table,
                                    auto_mode_upload,
                                    int(auto_chunk_size_upload),
                                )
                                dt = time.time() - t0
                                load_logs.append(f"✅ {table}: inserted {n:,} ({dt:.1f}s)")
                                load_prog.progress(int(i / len(selected_tables) * 100))

                            st.code("\n".join(load_logs))
                            load_status.update(label="✅ Loaded into Firebolt", state="complete")
                            _load_all.clear()
                            _load_rfm.clear()
                            _load_reco_inputs.clear()
                            st.rerun()
                        except Exception as e:
                            load_status.update(label="❌ Load failed", state="error")
                            st.error(str(e))
                        finally:
                            cur.close()
                else:
                    st.info("No tables selected (or no matching CSVs found) to auto-load.")
            elif saved and not auto_load_after_upload:
                st.info("Auto-load is OFF. Turn it ON above to load into Firebolt immediately after upload.")

    if role == "Admin":
        st.divider()
        st.markdown("**Clear database (danger zone)**")
        st.caption("This will remove all rows from the project tables in Firebolt (tables stay, data is deleted).")

        with st.expander("Clear Firebolt tables"):
            confirm = st.text_input('Type **CLEAR** to confirm', value="", help="Safety confirmation")
            if st.button("Clear now", type="secondary", disabled=(confirm.strip().upper() != "CLEAR")):
                conn = _get_conn()
                cur = conn.cursor()
                try:
                    clear_logs: list[str] = []
                    for table in TABLES.keys():
                        cur.execute(f"TRUNCATE TABLE public.{table}")
                        clear_logs.append(f"✅ Truncated public.{table}")

                    st.success("Database cleared (tables truncated).")
                    st.code("\n".join(clear_logs))
                    _load_all.clear()
                    st.rerun()
                except Exception as e:
                    st.error("Clear failed.")
                    st.code(str(e))
                finally:
                    cur.close()

elif page == "Monitoring":
    st.subheader("Monitoring & Alerts")
    st.caption("Basic alert rules are stored in `public.alerts` and can be scheduled (hourly/nightly).")

    conn = _get_conn()
    cur = conn.cursor()
    try:
        # Import defensively to avoid Streamlit crash if module is stale/reloaded.
        import monitoring.alerts as malerts

        malerts.ensure_alerts_table(cur)
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Run alert rules now"):
                alerts = malerts.compute_alerts(cur)
                for a in alerts:
                    malerts.write_alert(cur, a)
                st.success(f"Saved {len(alerts)} alerts.")
                _load_all.clear()
                st.rerun()
            if role == "Admin":
                if st.button("Clear alerts table", type="secondary", key="clear_alerts_btn"):
                    if hasattr(malerts, "clear_alerts"):
                        malerts.clear_alerts(cur)  # type: ignore[attr-defined]
                        st.success("Cleared public.alerts")
                    else:
                        st.error("clear_alerts() is not available. Restart Streamlit to pick up latest code.")
                    st.rerun()
        with c2:
            st.info(
                "Purpose: keep a history of important events (sales drop/spike, traffic issues, predictive warnings). "
                "Duplicates are automatically suppressed (dedup window)."
            )

        cols, rows = malerts.fetch_recent_alerts(cur, limit=50)
        if not rows:
            st.info("No alerts yet.")
        else:
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, width="stretch", height=420)
    finally:
        cur.close()

elif page == "Settings":
    st.subheader("Settings")
    st.caption("Project configuration & environment checks.")
    try:
        s = get_firebolt_settings()
        st.write("**Firebolt**")
        st.write(f"- Database: `{s.get('database')}`")
        st.write(f"- Engine: `{s.get('engine_name')}`")
        st.write(f"- Account: `{s.get('account_name')}`")
    except Exception as e:
        st.error(str(e))

    st.write("**Session**")
    st.write(f"- User: `{st.session_state['user']['username']}`")
    st.write(f"- Role: `{role}`")

elif page == "User Management":
    if role != "Admin":
        st.error("Admin only.")
        st.stop()

    st.subheader("User Management")
    st.caption("Create / edit roles / reset passwords / delete users (stored in `config/users.json`).")

    st.markdown("### Current users")
    users = list_users_for_admin()
    st.dataframe(pd.DataFrame(users), width="stretch", height=260)

    st.divider()
    st.markdown("### Create user")
    c1, c2, c3 = st.columns(3)
    with c1:
        nu = st.text_input("Username", key="um_new_username")
    with c2:
        npw = st.text_input("Password", type="password", key="um_new_password")
    with c3:
        nrole = st.selectbox("Role", ["Viewer", "Analyst", "Admin"], index=0, key="um_new_role")

    if st.button("Create user", type="primary", key="um_create_btn"):
        try:
            admin_create_user(nu, npw, role=nrole)  # type: ignore[arg-type]
            st.success("User created.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.markdown("### Edit / reset / delete")
    usernames = [u["username"] for u in users]
    if not usernames:
        st.info("No users found.")
    else:
        target_user = st.selectbox("Select user", usernames, key="um_target_user")
        current_role = next((u["role"] for u in users if u["username"] == target_user), "Viewer")
        new_role = st.selectbox("Change role", ["Viewer", "Analyst", "Admin"], index=["Viewer","Analyst","Admin"].index(current_role), key="um_change_role")
        if st.button("Save role", key="um_save_role"):
            try:
                admin_set_role(target_user, new_role)  # type: ignore[arg-type]
                st.success("Role updated.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

        st.markdown("**Reset password**")
        rp = st.text_input("New password", type="password", key="um_reset_pw")
        if st.button("Reset password", key="um_reset_pw_btn"):
            try:
                admin_reset_password(target_user, rp)
                st.success("Password reset.")
            except Exception as e:
                st.error(str(e))

        st.markdown("**Delete user**")
        confirm_del = st.text_input("Type DELETE to confirm", key="um_delete_confirm")
        if st.button("Delete user", type="secondary", disabled=(confirm_del.strip().upper() != "DELETE"), key="um_delete_btn"):
            try:
                if target_user == st.session_state["user"]["username"]:
                    st.error("You cannot delete the currently logged-in user.")
                else:
                    admin_delete_user(target_user)
                    st.success("User deleted.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))



