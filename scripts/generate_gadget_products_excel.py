"""
Generate a realistic gadget/products Excel template that matches the project's schema.

Output:
  dataset/real_products_gadgets.xlsx

Columns match Firebolt table + loader expectations:
  product_id, product_name, category, price
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_path = project_root / "dataset" / "real_products_gadgets.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    products = [
        # Smartphones
        (1001, "Nova X1 128GB 5G", "Smartphone", 399.0),
        (1002, "Nova X1 256GB 5G", "Smartphone", 449.0),
        (1003, "Aurora S9 256GB 5G", "Smartphone", 699.0),
        (1004, "Aurora S9 Pro 512GB 5G", "Smartphone", 899.0),
        (1005, "PixelMax Lite 128GB", "Smartphone", 329.0),
        (1006, "PixelMax 256GB", "Smartphone", 579.0),
        # Laptops
        (1101, "ZenBook Air 13 (i5/16GB/512GB)", "Laptop", 899.0),
        (1102, "ZenBook Air 13 (i7/16GB/1TB)", "Laptop", 1099.0),
        (1103, "CreatorBook 15 (i7/32GB/1TB)", "Laptop", 1499.0),
        (1104, "GamePro 16 (R7/32GB/1TB/RTX)", "Laptop", 1699.0),
        (1105, "WorkMate 14 (i5/8GB/256GB)", "Laptop", 649.0),
        # Tablets
        (1201, "TabGo 10.9 128GB Wi‑Fi", "Tablet", 329.0),
        (1202, "TabGo 10.9 256GB Wi‑Fi", "Tablet", 399.0),
        (1203, "TabGo 12.9 256GB Wi‑Fi", "Tablet", 599.0),
        (1204, "NoteSlate 11 128GB LTE", "Tablet", 459.0),
        # Wearables
        (1301, "PulseWatch 4", "Wearable", 149.0),
        (1302, "PulseWatch 4 Pro", "Wearable", 229.0),
        (1303, "FitBand Active", "Wearable", 49.0),
        (1304, "FitBand Active+", "Wearable", 69.0),
        # Audio
        (1401, "SoundPods Mini", "Audio", 29.0),
        (1402, "SoundPods ANC", "Audio", 99.0),
        (1403, "OverEar Studio ANC", "Audio", 179.0),
        (1404, "Bluetooth Speaker Go", "Audio", 39.0),
        (1405, "Bluetooth Speaker Max", "Audio", 89.0),
        # Accessories
        (1501, "USB‑C Fast Charger 30W", "Accessory", 19.0),
        (1502, "USB‑C Fast Charger 65W", "Accessory", 39.0),
        (1503, "USB‑C Cable (1m)", "Accessory", 9.0),
        (1504, "USB‑C Cable (2m)", "Accessory", 12.0),
        (1505, "Wireless Charger Pad 15W", "Accessory", 29.0),
        (1506, "Power Bank 10,000mAh", "Accessory", 25.0),
        (1507, "Power Bank 20,000mAh", "Accessory", 39.0),
        (1508, "Laptop Sleeve 13\"", "Accessory", 15.0),
        (1509, "Laptop Sleeve 15\"", "Accessory", 18.0),
        (1510, "Bluetooth Mouse", "Accessory", 17.0),
        (1511, "Mechanical Keyboard (TKL)", "Accessory", 79.0),
        # Storage
        (1601, "SSD Portable 1TB USB‑C", "Storage", 89.0),
        (1602, "SSD Portable 2TB USB‑C", "Storage", 149.0),
        (1603, "MicroSD 128GB U3", "Storage", 16.0),
        (1604, "MicroSD 256GB U3", "Storage", 27.0),
        # Networking
        (1701, "Wi‑Fi 6 Router AX1800", "Networking", 59.0),
        (1702, "Wi‑Fi 6 Router AX3000", "Networking", 89.0),
        (1703, "Mesh Wi‑Fi 6 (2‑pack)", "Networking", 149.0),
        (1704, "USB‑C Ethernet Adapter", "Networking", 14.0),
        # Smart Home
        (1801, "Smart Plug Mini", "Smart Home", 12.0),
        (1802, "Smart Bulb RGB", "Smart Home", 15.0),
        (1803, "Smart Bulb White", "Smart Home", 11.0),
        (1804, "Indoor Camera 1080p", "Smart Home", 29.0),
        (1805, "Video Doorbell", "Smart Home", 79.0),
        (1806, "Smart Thermostat", "Smart Home", 119.0),
        # Gaming
        (1901, "GamePad Wireless Controller", "Gaming", 39.0),
        (1902, "Gaming Headset", "Gaming", 49.0),
        (1903, "RGB Mousepad XL", "Gaming", 19.0),
        # Cameras
        (2001, "ActionCam 4K", "Camera", 99.0),
        (2002, "ActionCam 4K Pro", "Camera", 149.0),
    ]

    df = pd.DataFrame(products, columns=["product_id", "product_name", "category", "price"])

    notes = pd.DataFrame(
        [
            ["How to use", "Edit rows, then export the 'products' sheet as CSV named products.csv"],
            ["Required columns", "product_id, product_name, category, price"],
            ["Loader", "Use Dashboard → Data Pipeline OR scripts/load_dataset_to_firebolt.py"],
        ],
        columns=["Item", "Value"],
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="products", index=False)
        notes.to_excel(writer, sheet_name="notes", index=False)

    # Avoid unicode output issues on some Windows consoles.
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()


