"""
Run alert rules and persist them into Firebolt `public.alerts`.

Usage:
  python .\scripts\run_alerts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from firebolt_utils import connect_firebolt
from monitoring.alerts import compute_alerts, ensure_alerts_table, write_alert


def main() -> None:
    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        ensure_alerts_table(cur)
        alerts = compute_alerts(cur)
        for a in alerts:
            write_alert(cur, a)
        print(f"✅ Alerts computed: {len(alerts)}")
        for a in alerts:
            print(f"- [{a.severity}] {a.metric}: {a.message}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()


