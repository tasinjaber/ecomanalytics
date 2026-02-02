import os
from pathlib import Path

from firebolt.client.auth import ClientCredentials
from firebolt.db import connect

# Firebolt connection settings are read from environment variables so secrets
# are not hardcoded in source control.
#
# Required:
# - FIREBOLT_SERVICE_ACCOUNT_ID
# - FIREBOLT_SERVICE_ACCOUNT_SECRET
#
# Optional (defaults below are safe to change):
# - FIREBOLT_ACCOUNT_NAME
# - FIREBOLT_ENGINE_NAME
# - FIREBOLT_DATABASE

DEFAULT_ACCOUNT_NAME = "tasinjaber-1"
DEFAULT_ENGINE_NAME = "my_engine"
DEFAULT_DATABASE = "ecommerce_db"


def _load_dotenv_if_present() -> None:
    """
    Lightweight .env loader (no external dependency).
    If a project-root ".env" file exists, load KEY=VALUE pairs into the process
    environment *only if* those keys are not already set.
    """
    project_root = Path(__file__).resolve().parents[1]
    dotenv_path = project_root / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _get_env_settings() -> dict:
    _load_dotenv_if_present()

    missing: list[str] = []

    service_account_id = os.getenv("FIREBOLT_SERVICE_ACCOUNT_ID")
    service_account_secret = os.getenv("FIREBOLT_SERVICE_ACCOUNT_SECRET")

    if not service_account_id:
        missing.append("FIREBOLT_SERVICE_ACCOUNT_ID")
    if not service_account_secret:
        missing.append("FIREBOLT_SERVICE_ACCOUNT_SECRET")

    if missing:
        raise SystemExit(
            "Missing required Firebolt environment variables: "
            + ", ".join(missing)
            + "\n\nSet them in your shell before running this script, e.g. (PowerShell):\n"
            + '  $env:FIREBOLT_SERVICE_ACCOUNT_ID="..."\n'
            + '  $env:FIREBOLT_SERVICE_ACCOUNT_SECRET="..."\n'
            + '  $env:FIREBOLT_ACCOUNT_NAME="..."  # optional\n'
            + '  $env:FIREBOLT_ENGINE_NAME="..."   # optional\n'
            + '  $env:FIREBOLT_DATABASE="..."      # optional\n'
        )

    return {
        "service_account_id": service_account_id,
        "service_account_secret": service_account_secret,
        "account_name": os.getenv("FIREBOLT_ACCOUNT_NAME", DEFAULT_ACCOUNT_NAME),
        "engine_name": os.getenv("FIREBOLT_ENGINE_NAME", DEFAULT_ENGINE_NAME),
        "database": os.getenv("FIREBOLT_DATABASE", DEFAULT_DATABASE),
    }

def get_connection():
    s = _get_env_settings()
    conn = connect(
        auth=ClientCredentials(s["service_account_id"], s["service_account_secret"]),
        account_name=s["account_name"],
        engine_name=s["engine_name"],
        database=s["database"],
    )
    return conn

def create_tables(cursor):
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS customers (
          customer_id BIGINT,
          first_name TEXT,
          last_name TEXT,
          email TEXT,
          signup_date TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS products (
          product_id BIGINT,
          product_name TEXT,
          category TEXT,
          price DOUBLE,
          cost DOUBLE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
          order_id BIGINT,
          customer_id BIGINT,
          order_date TIMESTAMP,
          total_amount DOUBLE,
          city TEXT,
          country TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS order_items (
          order_item_id BIGINT,
          order_id BIGINT,
          product_id BIGINT,
          quantity INT,
          item_price DOUBLE,
          purchase_price DOUBLE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS page_views (
          event_id BIGINT,
          customer_id BIGINT,
          page_url TEXT,
          event_time TIMESTAMP,
          session_id TEXT
        );
        """
    ]

    print("🛠 Creating tables in Firebolt...")
    for stmt in tables_sql:
        cursor.execute(stmt)

    # Upgrade existing tables (if they were created before we added new columns)
    # Firebolt supports ADD COLUMN IF NOT EXISTS.
    cursor.execute("ALTER TABLE public.products ADD COLUMN IF NOT EXISTS cost DOUBLE")
    cursor.execute("ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS city TEXT")
    cursor.execute("ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS country TEXT")
    cursor.execute("ALTER TABLE public.order_items ADD COLUMN IF NOT EXISTS purchase_price DOUBLE")
    print("✅ Tables created successfully.")


def insert_sample_data(cursor):
    sample_data_sql = [
        # Customers
        """
        INSERT INTO customers VALUES
        (1, 'John', 'Doe', 'john@example.com', '2024-01-10'),
        (2, 'Sarah', 'Wilson', 'sarah@example.com', '2024-02-05'),
        (3, 'Michael', 'Lee', 'michael@example.com', '2024-03-15');
        """,

        # Products
        """
        INSERT INTO products VALUES
        (101, 'Laptop', 'Electronics', 999.99),
        (102, 'Mouse', 'Accessories', 19.99),
        (103, 'Headphones', 'Accessories', 49.99);
        """,

        # Orders
        """
        INSERT INTO orders VALUES
        (1001, 1, '2024-03-01', 1019.98),
        (1002, 2, '2024-03-05', 49.99);
        """,

        # Order Items
        """
        INSERT INTO order_items VALUES
        (1, 1001, 101, 1, 999.99),
        (2, 1001, 102, 1, 19.99),
        (3, 1002, 103, 1, 49.99);
        """,

        # Page Views
        """
        INSERT INTO page_views VALUES
        (501, 1, '/home', '2024-03-10 10:15:00', 'A1'),
        (502, 1, '/product/101', '2024-03-10 10:16:20', 'A1'),
        (503, 2, '/home', '2024-03-11 12:00:10', 'B1'),
        (504, 3, '/product/103', '2024-03-15 14:22:30', 'C1');
        """
    ]

    print("📥 Inserting sample data...")
    for stmt in sample_data_sql:
        cursor.execute(stmt)
    print("✅ Sample data inserted successfully.")


def test_queries(cursor):
    queries = {
        "Customers": "SELECT * FROM customers;",
        "Products": "SELECT * FROM products;",
        "Orders with Customers": """
            SELECT o.order_id, o.order_date, o.total_amount,
                   c.first_name, c.last_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id;
        """,
        "Top Viewed Pages": """
            SELECT page_url, COUNT(*) AS views
            FROM page_views
            GROUP BY page_url
            ORDER BY views DESC;
        """
    }

    for name, query in queries.items():
        print(f"\n🔹 {name}")
        cursor.execute(query)
        for row in cursor.fetchall():
            print(row)


if __name__ == "__main__":
    print("🔗 Connecting to Firebolt...")
    conn = get_connection()
    cursor = conn.cursor()
    print("✅ Connected.")

    create_tables(cursor)
    insert_sample_data(cursor)
    test_queries(cursor)

    cursor.close()
    conn.close()
    print("\n🏁 Done.")
