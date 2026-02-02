import csv
import random
import uuid
import os
import argparse
from datetime import datetime
import faker

fake = faker.Faker()

def ensure_dataset_dir(base_dir="dataset"):
    """
    Ensure the dataset directory exists.
    """
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    return base_dir

def generate_customers(n, out_path):
    with open(out_path, "w", newline='', encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "first_name", "last_name", "email", "signup_date"])
        for i in range(1, n + 1):
            d = fake.date_time_between(start_date='-2y', end_date='now')
            w.writerow([
                i,
                fake.first_name(),
                fake.last_name(),
                f"user{i}@example.com",
                d.isoformat()
            ])

def generate_products(n, out_path):
    cats = ["electronics", "books", "home", "clothing", "toys"]
    with open(out_path, "w", newline='', encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "product_name", "category", "price"])
        for i in range(1, n + 1):
            w.writerow([
                i,
                f"Product {i}",
                random.choice(cats),
                round(random.uniform(5, 500), 2)
            ])

def generate_orders_and_items(customers_n, products_n, orders_n, orders_out, items_out):
    with open(orders_out, "w", newline='', encoding="utf-8") as fo, \
         open(items_out, "w", newline='', encoding="utf-8") as fi:
        wo = csv.writer(fo)
        wi = csv.writer(fi)

        wo.writerow(["order_id", "customer_id", "order_date", "total_amount"])
        wi.writerow(["order_item_id", "order_id", "product_id", "quantity", "item_price"])

        order_item_id = 1
        for oid in range(1, orders_n + 1):
            cid = random.randint(1, customers_n)
            odt = fake.date_time_between(start_date='-1y', end_date='now')
            num_items = random.choice([1, 2, 3, 4])
            total = 0.0
            items = []

            for _ in range(num_items):
                pid = random.randint(1, products_n)
                q = random.randint(1, 3)
                price = round(random.uniform(5, 500), 2)
                total += price * q
                items.append((order_item_id, oid, pid, q, price))
                order_item_id += 1

            wo.writerow([oid, cid, odt.isoformat(), round(total, 2)])
            for it in items:
                wi.writerow(it)

def generate_page_views(customers_n, events_n, out_path):
    urls = ["/home", "/product", "/cart", "/checkout", "/search"]
    with open(out_path, "w", newline='', encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "customer_id", "page_url", "event_time", "session_id"])
        for i in range(1, events_n + 1):
            cid = random.randint(1, customers_n)
            url = random.choice(urls)
            et = fake.date_time_between(start_date='-1y', end_date='now')
            sid = str(uuid.uuid4())
            w.writerow([i, cid, url, et.isoformat(), sid])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=5000)
    parser.add_argument("--products", type=int, default=500)
    parser.add_argument("--orders", type=int, default=50000)
    parser.add_argument("--events", type=int, default=100000)
    args = parser.parse_args()

    # Base project directory = folder where you run the script from
    base_dir = os.path.dirname(os.path.abspath(__file__))          # ...\firebolt_project\scripts
    project_root = os.path.dirname(base_dir)                        # ...\firebolt_project

    dataset_dir = ensure_dataset_dir(os.path.join(project_root, "dataset"))

    customers_path = os.path.join(dataset_dir, "customers.csv")
    products_path = os.path.join(dataset_dir, "products.csv")
    orders_path = os.path.join(dataset_dir, "orders.csv")
    order_items_path = os.path.join(dataset_dir, "order_items.csv")
    page_views_path = os.path.join(dataset_dir, "page_views.csv")

    print("Generating customers...")
    generate_customers(args.customers, customers_path)

    print("Generating products...")
    generate_products(args.products, products_path)

    print("Generating orders and items...")
    generate_orders_and_items(
        args.customers,
        args.products,
        args.orders,
        orders_path,
        order_items_path
    )

    print("Generating page views...")
    generate_page_views(args.customers, args.events, page_views_path)

    print("✔ All CSV files generated in:", dataset_dir)
