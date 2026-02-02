"""
Generate a realistic multi-sheet Excel workbook matching the project's upload schema.

Output:
  dataset/sample_upload_template_realistic.xlsx

Sheets:
  customers, products, orders, order_items, page_views, notes
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def main() -> None:
    random.seed(42)
    fake = Faker()
    Faker.seed(42)

    project_root = Path(__file__).resolve().parents[1]
    # Use a new filename to avoid Windows file-lock issues if the previous workbook is open.
    out_path = project_root / "dataset" / "sample_upload_template_realistic_v2.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Products (gadgets-focused) ---
    products = [
        (1001, "Nova X1 128GB 5G", "Smartphone", 399.0),
        (1002, "Aurora S9 256GB 5G", "Smartphone", 699.0),
        (1003, "Aurora S9 Pro 512GB 5G", "Smartphone", 899.0),
        (1101, "ZenBook Air 13 (i5/16GB/512GB)", "Laptop", 899.0),
        (1102, "CreatorBook 15 (i7/32GB/1TB)", "Laptop", 1499.0),
        (1201, "TabGo 10.9 128GB Wi‑Fi", "Tablet", 329.0),
        (1301, "PulseWatch 4", "Wearable", 149.0),
        (1302, "PulseWatch 4 Pro", "Wearable", 229.0),
        (1401, "SoundPods Mini", "Audio", 29.0),
        (1402, "SoundPods ANC", "Audio", 99.0),
        (1403, "OverEar Studio ANC", "Audio", 179.0),
        (1501, "USB‑C Fast Charger 30W", "Accessory", 19.0),
        (1502, "USB‑C Fast Charger 65W", "Accessory", 39.0),
        (1503, "USB‑C Cable (1m)", "Accessory", 9.0),
        (1504, "Wireless Charger Pad 15W", "Accessory", 29.0),
        (1505, "Power Bank 10,000mAh", "Accessory", 25.0),
        (1510, "Bluetooth Mouse", "Accessory", 17.0),
        (1511, "Mechanical Keyboard (TKL)", "Accessory", 79.0),
        (1601, "SSD Portable 1TB USB‑C", "Storage", 89.0),
        (1701, "Wi‑Fi 6 Router AX1800", "Networking", 59.0),
        (1801, "Smart Plug Mini", "Smart Home", 12.0),
        (1804, "Indoor Camera 1080p", "Smart Home", 29.0),
        (1901, "GamePad Wireless Controller", "Gaming", 39.0),
        (1902, "Gaming Headset", "Gaming", 49.0),
        (2001, "ActionCam 4K", "Camera", 99.0),
    ]
    # Add a simple cost model (purchase cost) for future profit analytics.
    products_rows = []
    for pid, name, cat, price in products:
        cost = round(float(price) * random.uniform(0.55, 0.75), 2)
        products_rows.append((pid, name, cat, float(price), float(cost)))
    products_df = pd.DataFrame(products_rows, columns=["product_id", "product_name", "category", "price", "cost"])
    price_by_pid = {int(p[0]): float(p[3]) for p in products}
    cost_by_pid = {int(r[0]): float(r[4]) for r in products_rows}

    # --- Customers ---
    n_customers = 120
    customers_rows = []
    base_signup = datetime(2025, 7, 1, 9, 0, 0)
    for cid in range(1, n_customers + 1):
        fn = fake.first_name()
        ln = fake.last_name()
        email = f"user{cid}@example.com"
        signup = base_signup + timedelta(days=random.randint(0, 180), minutes=random.randint(0, 60 * 24))
        customers_rows.append([cid, fn, ln, email, _iso(signup)])
    customers_df = pd.DataFrame(customers_rows, columns=["customer_id", "first_name", "last_name", "email", "signup_date"])

    # --- Orders + Order Items (with realistic bundles/also-bought patterns) ---
    n_orders = 450
    orders_rows = []
    order_items_rows = []

    # Bundles to encourage "also bought"
    bundles = {
        1001: [1501, 1503, 1504, 1505],  # phone -> charger/cable/wireless charger/power bank
        1002: [1402, 1501, 1503],
        1101: [1510, 1511, 1601],  # laptop -> mouse/keyboard/ssd
        1201: [1504, 1503],
        1402: [1503, 1505],
        1804: [1801],  # camera -> smart plug
        1902: [1901],  # headset -> controller
    }

    base_order_date = datetime(2025, 10, 1, 10, 0, 0)
    order_id_start = 5000
    order_item_id = 90000

    for i in range(n_orders):
        oid = order_id_start + i + 1
        cid = random.randint(1, n_customers)
        odt = base_order_date + timedelta(days=random.randint(0, 110), minutes=random.randint(0, 60 * 24))

        # Pick a primary product with weighted probability (phones/laptops more common)
        primary_pool = [1001, 1002, 1101, 1201, 1402, 1301, 1601, 1701, 1804, 1902, 2001]
        primary = random.choice(primary_pool)

        pids = [primary]
        # Add bundle items with some probability
        for b in bundles.get(primary, []):
            if random.random() < 0.45:
                pids.append(b)
        # Add 0-2 random extras
        extras = random.sample([p[0] for p in products], k=random.randint(0, 2))
        for e in extras:
            if e not in pids and random.random() < 0.25:
                pids.append(int(e))

        # Slovenia cities (mix)
        slovenia_cities = [
            "Ljubljana",
            "Maribor",
            "Celje",
            "Kranj",
            "Koper",
            "Novo Mesto",
            "Ptuj",
            "Velenje",
            "Murska Sobota",
            "Nova Gorica",
        ]
        city = random.choice(slovenia_cities)
        country = "Slovenia"

        # Create order_items and compute totals (revenue) + purchase_price (cost)
        total = 0.0
        for pid in pids:
            order_item_id += 1
            qty = 1 if random.random() < 0.9 else 2
            price = price_by_pid[int(pid)]
            item_price = float(price)
            total += qty * item_price
            purchase_price = float(cost_by_pid.get(int(pid), item_price * 0.65))
            order_items_rows.append(
                [order_item_id, oid, int(pid), int(qty), float(item_price), float(purchase_price)]
            )

        orders_rows.append([oid, cid, _iso(odt), round(total, 2), city, country])

    orders_df = pd.DataFrame(
        orders_rows, columns=["order_id", "customer_id", "order_date", "total_amount", "city", "country"]
    )
    order_items_df = pd.DataFrame(
        order_items_rows, columns=["order_item_id", "order_id", "product_id", "quantity", "item_price", "purchase_price"]
    )

    # --- Page views (small but useful) ---
    # For each order, create a session with home -> product pages -> checkout
    page_views_rows = []
    event_id = 70000
    for _, o in orders_df.sample(n=min(250, len(orders_df)), random_state=42).iterrows():
        cid = int(o["customer_id"])
        oid = int(o["order_id"])
        # session id derived
        session = f"S{oid}"
        start = datetime.fromisoformat(str(o["order_date"]))
        urls = ["/home", "/search", f"/order/{oid}", "/checkout"]
        # add some product pages from that order
        pids = order_items_df.loc[order_items_df["order_id"] == oid, "product_id"].tolist()
        for pid in pids[:3]:
            urls.insert(2, f"/product/{int(pid)}")
        for j, url in enumerate(urls):
            event_id += 1
            t = start + timedelta(minutes=2 * j + random.randint(0, 1))
            page_views_rows.append([event_id, cid, url, _iso(t), session])

    page_views_df = pd.DataFrame(
        page_views_rows, columns=["event_id", "customer_id", "page_url", "event_time", "session_id"]
    )

    notes = pd.DataFrame(
        [
            ["Upload", "Dashboard → Data Pipeline → Upload dataset (CSV or Excel)"],
            ["Excel mode", "Upload this single .xlsx; the app will generate dataset/*.csv automatically."],
            ["Sheets", "customers, products, orders, order_items, page_views"],
            ["Tip", "After upload, choose mode=replace and click 'Load dataset into Firebolt'."],
        ],
        columns=["Item", "Value"],
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        customers_df.to_excel(writer, sheet_name="customers", index=False)
        products_df.to_excel(writer, sheet_name="products", index=False)
        orders_df.to_excel(writer, sheet_name="orders", index=False)
        order_items_df.to_excel(writer, sheet_name="order_items", index=False)
        page_views_df.to_excel(writer, sheet_name="page_views", index=False)
        notes.to_excel(writer, sheet_name="notes", index=False)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()


