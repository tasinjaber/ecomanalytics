"""
Generate a multi-sheet Excel workbook that matches the project's upload schema.

Output:
  dataset/sample_upload_template.xlsx

Sheets:
  customers, products, orders, order_items, page_views
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_path = project_root / "dataset" / "sample_upload_template.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    customers = pd.DataFrame(
        [
            [1, "Ayesha", "Rahman", "ayesha@example.com", "2025-12-01T10:05:00"],
            [2, "Nafis", "Khan", "nafis@example.com", "2025-12-03T09:30:00"],
            [3, "Sadia", "Islam", "sadia@example.com", "2025-12-10T14:20:00"],
        ],
        columns=["customer_id", "first_name", "last_name", "email", "signup_date"],
    )

    products = pd.DataFrame(
        [
            [1001, "Nova X1 128GB 5G", "Smartphone", 399.0],
            [1501, "USB‑C Fast Charger 30W", "Accessory", 19.0],
            [1402, "SoundPods ANC", "Audio", 99.0],
            [1101, "ZenBook Air 13 (i5/16GB/512GB)", "Laptop", 899.0],
        ],
        columns=["product_id", "product_name", "category", "price"],
    )

    orders = pd.DataFrame(
        [
            [5001, 1, "2026-01-05T11:10:00", 418.0],
            [5002, 2, "2026-01-06T16:40:00", 99.0],
            [5003, 1, "2026-01-10T18:05:00", 918.0],
        ],
        columns=["order_id", "customer_id", "order_date", "total_amount"],
    )

    order_items = pd.DataFrame(
        [
            [90001, 5001, 1001, 1, 399.0],
            [90002, 5001, 1501, 1, 19.0],
            [90003, 5002, 1402, 1, 99.0],
            [90004, 5003, 1101, 1, 899.0],
            [90005, 5003, 1501, 1, 19.0],
        ],
        columns=["order_item_id", "order_id", "product_id", "quantity", "item_price"],
    )

    page_views = pd.DataFrame(
        [
            [70001, 1, "/home", "2026-01-05T10:59:00", "S1"],
            [70002, 1, "/product/1001", "2026-01-05T11:02:00", "S1"],
            [70003, 1, "/checkout", "2026-01-05T11:08:00", "S1"],
            [70004, 2, "/home", "2026-01-06T16:10:00", "S2"],
            [70005, 2, "/product/1402", "2026-01-06T16:25:00", "S2"],
        ],
        columns=["event_id", "customer_id", "page_url", "event_time", "session_id"],
    )

    notes = pd.DataFrame(
        [
            ["How to upload", "Dashboard → Data Pipeline → Upload dataset (CSV or Excel)"],
            ["Excel mode", "Upload this single .xlsx; the app will create dataset/*.csv automatically."],
            ["Sheet names", "customers, products, orders, order_items, page_views"],
            ["Column names", "Must match exactly (see each sheet header)."],
        ],
        columns=["Item", "Value"],
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        customers.to_excel(writer, sheet_name="customers", index=False)
        products.to_excel(writer, sheet_name="products", index=False)
        orders.to_excel(writer, sheet_name="orders", index=False)
        order_items.to_excel(writer, sheet_name="order_items", index=False)
        page_views.to_excel(writer, sheet_name="page_views", index=False)
        notes.to_excel(writer, sheet_name="notes", index=False)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()


