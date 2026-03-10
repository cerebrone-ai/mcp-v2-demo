import sqlite3
import os

DB_FILE = "enterprise.db"

def setup_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create Customers Table
    cursor.execute('''
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            status TEXT
        )
    ''')
    
    # Create Financials Table (Sensitive)
    cursor.execute('''
        CREATE TABLE financials (
            customer_id TEXT PRIMARY KEY,
            lifetime_value REAL,
            credit_card_last_4 TEXT,
            last_payment_date TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        )
    ''')
    
    # Create Support Tickets Table
    cursor.execute('''
        CREATE TABLE support_tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_id TEXT,
            issue TEXT,
            status TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
        )
    ''')
    
    # Insert Mock Data
    cursor.execute("INSERT INTO customers VALUES ('cust-123', 'Acme Corp', 'contact@acme.com', 'Active')")
    cursor.execute("INSERT INTO customers VALUES ('cust-456', 'Globex', 'info@globex.com', 'Churned')")
    
    cursor.execute("INSERT INTO financials VALUES ('cust-123', 45000.50, '4242', '2023-11-01')")
    cursor.execute("INSERT INTO financials VALUES ('cust-456', 1200.00, '1111', '2022-05-15')")
    
    cursor.execute("INSERT INTO support_tickets VALUES ('tkt-001', 'cust-123', 'API Rate limit issue', 'Resolved')")
    cursor.execute("INSERT INTO support_tickets VALUES ('tkt-002', 'cust-123', 'Need help with billing', 'Open')")
    cursor.execute("INSERT INTO support_tickets VALUES ('tkt-003', 'cust-456', 'Account cancellation', 'Resolved')")
    
    conn.commit()
    conn.close()
    print("Database enterprise.db created and populated to simulate an internal corporate DB.")

if __name__ == "__main__":
    setup_db()
