"""
Production-ish scheduler: runs ingestion + alerts on a schedule.

This is intentionally simple for coursework:
- Incremental load (watermark) from ./dataset
- Alert rules into public.alerts

Run:
  python .\pipelines\scheduler.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from firebolt_utils import connect_firebolt
from monitoring.alerts import compute_alerts, ensure_alerts_table, write_alert
from scripts.load_dataset_to_firebolt import TABLES, load_table


def run_incremental_load():
    dataset_dir = Path(os.getenv("DATASET_DIR", str(PROJECT_ROOT / "dataset")))
    chunk_size = int(os.getenv("LOAD_CHUNK_SIZE", "5000"))
    tables = os.getenv("LOAD_TABLES", "orders,order_items,page_views").split(",")
    tables = [t.strip() for t in tables if t.strip()]

    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        for t in tables:
            if t not in TABLES:
                continue
            if t in ["orders", "order_items", "page_views"]:
                mode = "incremental"
            else:
                mode = "append"
            load_table(cur, dataset_dir, t, mode=mode, chunk_size=chunk_size)
    finally:
        cur.close()
        conn.close()


def run_alerts():
    conn = connect_firebolt()
    cur = conn.cursor()
    try:
        ensure_alerts_table(cur)
        alerts = compute_alerts(cur)
        for a in alerts:
            write_alert(cur, a)
    finally:
        cur.close()
        conn.close()


def main():
    sched = BlockingScheduler(timezone="UTC")

    # Default schedules (override via env if you want):
    # - incremental load every 30 minutes
    # - alerts every 60 minutes
    sched.add_job(run_incremental_load, "interval", minutes=int(os.getenv("LOAD_EVERY_MIN", "30")))
    sched.add_job(run_alerts, "interval", minutes=int(os.getenv("ALERTS_EVERY_MIN", "60")))

    print("✅ Scheduler started.")
    print(" - Incremental load interval (min):", os.getenv("LOAD_EVERY_MIN", "30"))
    print(" - Alerts interval (min):", os.getenv("ALERTS_EVERY_MIN", "60"))
    print("Stop with Ctrl+C")

    sched.start()


if __name__ == "__main__":
    main()


