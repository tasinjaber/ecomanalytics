from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class Alert:
    severity: str  # INFO/WARN/CRITICAL
    metric: str
    message: str
    value: float | int | None = None


def ensure_alerts_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
          alert_time TIMESTAMP,
          severity TEXT,
          metric TEXT,
          message TEXT,
          value DOUBLE
        );
        """
    )


def clear_alerts(cursor) -> None:
    cursor.execute("TRUNCATE TABLE public.alerts")


def write_alert(cursor, alert: Alert) -> None:
    """
    Write an alert, with lightweight de-duplication to avoid repeated inserts.
    If the same (metric, message) was inserted recently, skip.
    """
    # De-dup window (minutes). Default: 360 minutes (6 hours).
    try:
        dedup_min = int(os.getenv("ALERT_DEDUP_MIN", "360"))
    except Exception:
        dedup_min = 360

    # Firebolt doesn't reliably support bind params inside INTERVAL literals.
    # So we embed a sanitized integer into the SQL.
    dedup_min = int(max(1, min(dedup_min, 7 * 24 * 60)))

    try:
        cursor.execute(
            f"""
            SELECT COUNT(*) AS cnt
            FROM public.alerts
            WHERE metric = %s
              AND message = %s
              AND alert_time >= NOW() - INTERVAL '{dedup_min} minutes'
            """,
            (alert.metric, alert.message),
        )
        cnt = int(cursor.fetchone()[0] or 0)
        if cnt > 0:
            return
    except Exception:
        # If de-dup check fails, still insert.
        pass

    cursor.execute(
        """
        INSERT INTO public.alerts (alert_time, severity, metric, message, value)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            datetime.now(timezone.utc).astimezone().replace(tzinfo=None),
            alert.severity,
            alert.metric,
            alert.message,
            float(alert.value) if alert.value is not None else None,
        ),
    )


def compute_alerts(cursor) -> list[Alert]:
    """
    Basic production-style alert rules (simple, exam-friendly):
    - Sales drop in last 7 days vs previous 7 days
    - Traffic spike/drop in last 7 days vs previous 7 days
    """
    alerts: list[Alert] = []

    # Use the dataset's latest timestamps (MAX(order_date)/MAX(event_time)) so results are stable
    # even when historical datasets are loaded (not dependent on NOW()).
    cursor.execute(
        """
        WITH asof AS (
          SELECT MAX(order_date) AS as_of
          FROM public.orders
        ),
        w AS (
          SELECT
            SUM(CASE WHEN o.order_date >= a.as_of - INTERVAL '7 days' THEN o.total_amount ELSE 0 END) AS rev_7d,
            SUM(CASE WHEN o.order_date >= a.as_of - INTERVAL '14 days'
                      AND o.order_date < a.as_of - INTERVAL '7 days' THEN o.total_amount ELSE 0 END) AS rev_prev_7d
          FROM public.orders o
          CROSS JOIN asof a
        )
        SELECT COALESCE(rev_7d,0), COALESCE(rev_prev_7d,0) FROM w
        """
    )
    rev_7d, rev_prev = cursor.fetchone()
    rev_7d = float(rev_7d or 0.0)
    rev_prev = float(rev_prev or 0.0)

    if rev_prev > 0:
        change = (rev_7d - rev_prev) / rev_prev
        if change <= -0.3:
            alerts.append(
                Alert(
                    severity="CRITICAL",
                    metric="revenue_7d",
                    message=f"Revenue dropped {change:.0%} vs previous 7 days",
                    value=rev_7d,
                )
            )
        elif change <= -0.15:
            alerts.append(
                Alert(
                    severity="WARN",
                    metric="revenue_7d",
                    message=f"Revenue dropped {change:.0%} vs previous 7 days",
                    value=rev_7d,
                )
            )

    cursor.execute(
        """
        WITH asof AS (
          SELECT MAX(event_time) AS as_of
          FROM public.page_views
        ),
        w AS (
          SELECT
            COUNT(*) FILTER (WHERE pv.event_time >= a.as_of - INTERVAL '7 days') AS views_7d,
            COUNT(*) FILTER (WHERE pv.event_time >= a.as_of - INTERVAL '14 days'
                              AND pv.event_time < a.as_of - INTERVAL '7 days') AS views_prev_7d
          FROM public.page_views pv
          CROSS JOIN asof a
        )
        SELECT COALESCE(views_7d,0), COALESCE(views_prev_7d,0) FROM w
        """
    )
    v7, vprev = cursor.fetchone()
    v7 = int(v7 or 0)
    vprev = int(vprev or 0)
    if vprev > 0:
        change = (v7 - vprev) / vprev
        if change >= 0.5:
            alerts.append(Alert("INFO", "traffic_7d", f"Traffic spiked {change:.0%} vs previous 7 days", v7))
        elif change <= -0.3:
            alerts.append(Alert("WARN", "traffic_7d", f"Traffic dropped {change:.0%} vs previous 7 days", v7))

    return alerts


def fetch_recent_alerts(cursor, limit: int = 50):
    cursor.execute(
        """
        SELECT alert_time, severity, metric, message, value
        FROM public.alerts
        ORDER BY alert_time DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description] if cursor.description else []
    return cols, rows


