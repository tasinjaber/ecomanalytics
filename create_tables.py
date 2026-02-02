from firebolt.db import connect
from firebolt.client.auth import ClientCredentials

SERVICE_ACCOUNT_ID = "penbCPXvya7qY7HpfMgCytj3oYIzptIT"   # service account ID
SERVICE_ACCOUNT_SECRET = "CtRgWMgLoDAMPSupMoHAHQIPRaoMbQFghQ-QEeLv-nU-x0D2Cz_asFVMPRkVWFZT"  # secret

ACCOUNT_NAME = "tasinjaber-1" 
ENGINE_NAME = "my_engine"    
DATABASE = "ecommerce_db"            

#Connect to Firebolt

def get_connection():
    conn = connect(
        auth=ClientCredentials(SERVICE_ACCOUNT_ID, SERVICE_ACCOUNT_SECRET),
        account_name=ACCOUNT_NAME,
        engine_name=ENGINE_NAME,
        database=DATABASE,
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
          price DOUBLE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS orders (
          order_id BIGINT,
          customer_id BIGINT,
          order_date TIMESTAMP,
          total_amount DOUBLE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS order_items (
          order_item_id BIGINT,
          order_id BIGINT,
          product_id BIGINT,
          quantity INT,
          item_price DOUBLE
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
