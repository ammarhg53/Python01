import sqlite3
import hashlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
from abc import ABC, abstractmethod
from fpdf import FPDF
import random
import os

# ==========================================
# 1. DATABASE MANAGER (Singleton)
# ==========================================
class DatabaseManager:
    _instance = None
    DB_NAME = "smart_inventory.db"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance.init_db()
        return cls._instance

    def get_connection(self):
        return sqlite3.connect(self.DB_NAME, check_same_thread=False)

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Enable Foreign Keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Users Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Categories
        cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )''')

        # Products
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category_id INTEGER,
            selling_price REAL,
            cost_price REAL,
            stock INTEGER,
            sales_count INTEGER DEFAULT 0,
            image_path TEXT,
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )''')

        # Customers
        cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
            mobile TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            total_spent REAL DEFAULT 0,
            total_visits INTEGER DEFAULT 0,
            cancelled_orders INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Orders
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_mobile TEXT,
            operator_username TEXT,
            total_amount REAL,
            gst_amount REAL,
            payment_mode TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            cancellation_reason TEXT,
            FOREIGN KEY(customer_mobile) REFERENCES customers(mobile)
        )''')

        # Order Items
        cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            product_id INTEGER,
            quantity INTEGER,
            price REAL,
            cost REAL,
            FOREIGN KEY(order_id) REFERENCES orders(order_id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )''')
        
        # Settings
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        conn.commit()
        
        # Check if users exist, if not seed data
        cursor.execute("SELECT count(*) FROM users")
        if cursor.fetchone()[0] == 0:
            self.seed_data(cursor, conn)
        
        conn.close()

    def seed_data(self, cursor, conn):
        # 1. Users
        admin_pass = hashlib.sha256("Admin@123".encode()).hexdigest()
        pos_pass = hashlib.sha256("Pos@123".encode()).hexdigest()
        
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("System Admin", "admin", admin_pass, "admin"))
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("POS Operator 1", "pos1", pos_pass, "pos"))
        
        # 2. Categories
        categories = ['Electronics', 'Groceries', 'Clothing', 'Stationery', 'Home Decor']
        for cat in categories:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
        
        # 3. Products (50 Dummy)
        for i in range(1, 51):
            cat_id = random.randint(1, 5)
            cost = random.randint(50, 500)
            selling = cost * random.uniform(1.2, 2.0)
            stock = random.randint(0, 100)
            cursor.execute('''INSERT INTO products (name, category_id, selling_price, cost_price, stock, image_path) 
                              VALUES (?, ?, ?, ?, ?, ?)''',
                           (f"Product {i}", cat_id, round(selling, 2), cost, stock, "https://via.placeholder.com/150"))

        # 4. Customers (50 Dummy)
        for i in range(1, 51):
            mobile = f"98765432{i:02d}"
            cursor.execute('''INSERT INTO customers (mobile, name, total_spent, total_visits) 
                              VALUES (?, ?, ?, ?)''', 
                           (mobile, f"Customer {i}", random.randint(1000, 50000), random.randint(1, 20)))

        # 5. Settings
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('store_name', 'SmartInventory Store')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gst_enabled', 'True')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('gst_percent', '18')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('upi_id', 'admin@upi')")

        # 6. Dummy Orders (Past Data for Analytics)
        # Generate sales for the past 60 days
        base_date = datetime.datetime(2026, 2, 9)
        for i in range(50):
            days_ago = random.randint(0, 60)
            order_date = base_date - datetime.timedelta(days=days_ago)
            order_id = f"ORD{random.randint(10000,99999)}"
            amt = random.randint(500, 5000)
            
            cursor.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode, timestamp)
                              VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (order_id, f"98765432{random.randint(1,50):02d}", "pos1", amt, amt*0.18, random.choice(['CASH', 'UPI', 'CARD']), order_date))

        conn.commit()

# ==========================================
# 2. OOPS ARCHITECTURE: USER MANAGEMENT
# ==========================================

class User(ABC):
    def __init__(self, user_id, username, role):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.db = DatabaseManager()

    @staticmethod
    def login(username, password):
        db = DatabaseManager()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT id, role FROM users WHERE username=? AND password_hash=?", (username, hashed))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if user[1] == 'admin':
                return Admin(user[0], username)
            else:
                return POSOperator(user[0], username)
        return None

    def change_password(self, new_password):
        # Complexity check handled in UI
        conn = self.db.get_connection()
        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, self.user_id))
        conn.commit()
        conn.close()

class Admin(User):
    def __init__(self, user_id, username):
        super().__init__(user_id, username, 'admin')

    def add_product(self, name, category_id, selling, cost, stock, image):
        conn = self.db.get_connection()
        conn.execute("INSERT INTO products (name, category_id, selling_price, cost_price, stock, image_path) VALUES (?,?,?,?,?,?)",
                     (name, category_id, selling, cost, stock, image))
        conn.commit()
        conn.close()
        
    def cancel_order(self, order_id, reason):
        conn = self.db.get_connection()
        # Restock logic could be added here
        conn.execute("UPDATE orders SET status='cancelled', cancellation_reason=? WHERE order_id=?", (reason, order_id))
        # Update customer stats
        cursor = conn.execute("SELECT customer_mobile FROM orders WHERE order_id=?", (order_id,))
        res = cursor.fetchone()
        if res:
            conn.execute("UPDATE customers SET cancelled_orders = cancelled_orders + 1 WHERE mobile=?", (res[0],))
        conn.commit()
        conn.close()

class POSOperator(User):
    def __init__(self, user_id, username):
        super().__init__(user_id, username, 'pos')

    def create_order(self, customer_mobile, cart_items, payment_mode, gst_config):
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        total = sum(item['price'] * item['qty'] for item in cart_items)
        gst_amt = 0
        if gst_config['enabled']:
            gst_amt = total * (gst_config['percent'] / 100)
            total += gst_amt
            
        order_id = f"BILL-{int(datetime.datetime.now().timestamp())}"
        
        # Create Order
        cursor.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (order_id, customer_mobile, self.username, total, gst_amt, payment_mode))
        
        # Add Items & Update Stock
        for item in cart_items:
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price, cost) VALUES (?, ?, ?, ?, ?)",
                           (order_id, item['id'], item['qty'], item['price'], item['cost']))
            
            cursor.execute("UPDATE products SET stock = stock - ?, sales_count = sales_count + ? WHERE id=?",
                           (item['qty'], item['qty'], item['id']))
            
        # Update Customer
        cursor.execute("UPDATE customers SET total_spent = total_spent + ?, total_visits = total_visits + 1 WHERE mobile=?",
                       (total, customer_mobile))
        
        conn.commit()
        conn.close()
        return order_id, total, gst_amt

# ==========================================
# 3. ANALYTICS ENGINE (Advanced)
# ==========================================
class AnalyticsEngine:
    def __init__(self):
        self.db = DatabaseManager()

    def get_sales_data(self, start_date, end_date):
        conn = self.db.get_connection()
        query = f"""
            SELECT date(timestamp) as date, SUM(total_amount) as sales, COUNT(order_id) as orders, SUM(total_amount - gst_amount) as net_sales
            FROM orders 
            WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY date(timestamp)
            ORDER BY date(timestamp)
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_linear_regression(self, df):
        # Prepare Data
        if df.empty:
            return None, None
            
        df['day_index'] = range(len(df))
        X = df['day_index'].values
        y = df['sales'].values

        # y = mx + c
        m, c = np.polyfit(X, y, 1)
        
        # Predict next 7 days
        future_X = np.arange(len(df), len(df) + 7)
        future_y = m * future_X + c
        
        return (X, m*X + c), (future_X, future_y)

    def get_category_sales(self):
        conn = self.db.get_connection()
        query = """
            SELECT c.name, SUM(oi.quantity) as qty, SUM(oi.price * oi.quantity) as revenue 
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            GROUP BY c.name
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_retention_rate(self):
        conn = self.db.get_connection()
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        returning_customers = conn.execute("SELECT COUNT(*) FROM customers WHERE total_visits > 1").fetchone()[0]
        conn.close()
        return (returning_customers / total_customers * 100) if total_customers > 0 else 0

# ==========================================
# 4. UTILS (Search & Security)
# ==========================================
def check_password_strength(password):
    score = 0
    if len(password) >= 8: score += 1
    if any(c.isupper() for c in password): score += 1
    if any(c.islower() for c in password): score += 1
    if any(c.isdigit() for c in password): score += 1
    if any(not c.isalnum() for c in password): score += 1
    return score

def generate_invoice_pdf(store_name, bill_no, customer, items, total, gst, operator):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=store_name, ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt=f"Bill No: {bill_no}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Operator: {operator}", ln=True, align='L')
    pdf.cell(200, 10, txt=f"Customer: {customer['name']} ({customer['mobile']})", ln=True, align='L')
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Price", 1)
    pdf.cell(40, 10, "Total", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    for item in items:
        pdf.cell(80, 10, item['name'], 1)
        pdf.cell(30, 10, str(item['qty']), 1)
        pdf.cell(40, 10, f"{item['price']:.2f}", 1)
        pdf.cell(40, 10, f"{item['price']*item['qty']:.2f}", 1)
        pdf.ln()
        
    pdf.ln(5)
    pdf.cell(150, 10, "GST Amount", 0)
    pdf.cell(40, 10, f"{gst:.2f}", 0, ln=True)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, "Grand Total", 0)
    pdf.cell(40, 10, f"{total:.2f}", 0, ln=True)
    
    filename = f"{customer['name'].replace(' ', '')}_{customer['mobile']}_{int(datetime.datetime.now().timestamp())}.pdf"
    pdf.output(filename)
    return filename
