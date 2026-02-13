import sqlite3
import hashlib
import pandas as pd
import numpy as np
import datetime
import random
import qrcode
import os
from abc import ABC, abstractmethod
from fpdf import FPDF

# ==========================================
# 1. DATABASE & SINGLETON PATTERN
# ==========================================
class DatabaseManager:
    _instance = None
    DB_NAME = "smart_inventory_pro.db"

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
        cursor.execute("PRAGMA foreign_keys = ON")

        # 1. Users
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # 2. Categories
        cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )''')

        # 3. Products
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

        # 4. Customers
        cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
            mobile TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            total_spent REAL DEFAULT 0,
            total_visits INTEGER DEFAULT 0,
            cancelled_orders INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # 5. Orders
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

        # 6. Order Items
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

        # 7. Settings
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        conn.commit()
        
        # Seed Data if empty
        cursor.execute("SELECT count(*) FROM users")
        if cursor.fetchone()[0] == 0:
            self.seed_data(cursor, conn)
        
        conn.close()

    def seed_data(self, cursor, conn):
        # Users
        admin_pass = hashlib.sha256("Admin@123".encode()).hexdigest()
        pos_pass = hashlib.sha256("Pos@123".encode()).hexdigest()
        
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("System Admin", "admin", admin_pass, "admin"))
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("POS Operator 1", "pos1", pos_pass, "pos"))
        
        # Realistic Categories
        categories = ['Uncategorized', 'Snacks', 'Beverages', 'Grocery', 'Dairy', 'Bakery', 
                      'Frozen', 'Personal Care', 'Stationery', 'Electronics', 'Household']
        cat_map = {}
        for cat in categories:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
            cat_map[cat] = cursor.lastrowid
        
        # Realistic Products Data
        products_data = {
            'Snacks': [('Lays Classic Salted', 20, 15), ('Doritos Nacho Cheese', 30, 22), ('Pringles Sour Cream', 110, 85), ('Kurkure Masala Munch', 20, 14)],
            'Beverages': [('Coca Cola 750ml', 45, 35), ('Pepsi 500ml', 40, 30), ('Red Bull Energy Drink', 125, 95), ('Tropicana Mixed Fruit', 110, 80)],
            'Grocery': [('India Gate Basmati Rice 1kg', 120, 95), ('Tata Salt 1kg', 25, 18), ('Aashirvaad Atta 5kg', 240, 210), ('Toor Dal 1kg', 160, 130)],
            'Dairy': [('Amul Butter 100g', 56, 48), ('Mother Dairy Milk 1L', 66, 60), ('Paneer 200g', 85, 70), ('Amul Cheese Slices', 140, 115)],
            'Bakery': [('Britannia White Bread', 45, 38), ('Chocolate Muffin', 60, 40), ('Butter Croissant', 80, 50)],
            'Personal Care': [('Dove Shampoo 180ml', 160, 120), ('Colgate Toothpaste', 90, 70), ('Nivea Body Lotion', 250, 190)],
            'Stationery': [('Classmate Notebook', 60, 40), ('Parker Pen', 250, 180), ('Fevicol 100g', 50, 35)],
            'Electronics': [('USB C Cable', 350, 150), ('Wireless Mouse', 600, 400), ('Earphones', 400, 250)],
            'Household': [('Vim Dishwash Gel', 110, 90), ('Surf Excel 1kg', 140, 120), ('Harpic Cleaner', 180, 150)]
        }

        # Insert 50+ Products
        count = 0
        for cat, items in products_data.items():
            cid = cat_map[cat]
            for name, sell, cost in items:
                stock = random.randint(20, 100)
                # Ensure non-zero sales count for analytics
                sales_count = random.randint(50, 500) 
                cursor.execute('''INSERT INTO products (name, category_id, selling_price, cost_price, stock, sales_count, image_path) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?)''',
                               (name, cid, float(sell), float(cost), stock, sales_count, "https://via.placeholder.com/150"))
                count += 1
        
        # Fill remaining to reach 50 if needed (using generic for fillers)
        while count < 55:
            cat = random.choice(list(products_data.keys()))
            cid = cat_map[cat]
            cost = random.randint(50, 500)
            sell = cost * random.uniform(1.2, 1.5)
            sales_count = random.randint(50, 200)
            cursor.execute('''INSERT INTO products (name, category_id, selling_price, cost_price, stock, sales_count, image_path) 
                              VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (f"{cat} Item {count}", cid, round(sell, 2), cost, 50, sales_count, "https://via.placeholder.com/150"))
            count += 1

        # Customers (50 records)
        for i in range(1, 51):
            mobile = f"98765432{i:02d}"
            cursor.execute("INSERT INTO customers (mobile, name, total_spent, total_visits) VALUES (?, ?, ?, ?)", 
                           (mobile, f"Customer {i}", random.randint(1000, 50000), random.randint(1, 20)))

        # Settings
        settings = {
            'store_name': 'SmartInventory Enterprise',
            'gst_enabled': 'True',
            'gst_percent': '18',
            'upi_id': 'merchant@okaxis'
        }
        for k, v in settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # Orders (History for Analytics - Past 60 days)
        base_date = datetime.datetime.now()
        for i in range(60): 
            days_ago = random.randint(0, 30)
            order_date = base_date - datetime.timedelta(days=days_ago)
            order_id = f"ORD{random.randint(10000,99999)}"
            amt = random.randint(500, 5000)
            cost = amt * 0.7 
            
            cursor.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode, timestamp)
                              VALUES (?, ?, ?, ?, ?, ?, ?)''',
                           (order_id, f"98765432{random.randint(1,50):02d}", "pos1", amt, amt*0.18, "CASH", order_date))
            
            # Insert dummy item for margin calc
            cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price, cost) VALUES (?, ?, ?, ?, ?)",
                           (order_id, random.randint(1,50), 1, amt, cost))

        conn.commit()

# ==========================================
# 2. ALGORITHMS (ACADEMIC CORE)
# ==========================================
class SearchAlgorithms:
    """
    Encapsulates Search Logic to demonstrate O(n) vs O(log n)
    """
    @staticmethod
    def linear_search(data_list, key, value):
        """
        O(n): Iterates through entire list. Good for unsorted/small data.
        """
        results = []
        for item in data_list:
            if str(item[key]).lower().startswith(str(value).lower()):
                results.append(item)
        return results

    @staticmethod
    def binary_search(data_list, key, value):
        """
        O(log n): Requires sorted data. Divides search space in half.
        """
        # Step 1: Sort (O(n log n)) - In a real DB, we assume indexed/sorted fetch, 
        # but for academic simulation, we sort in Python.
        sorted_data = sorted(data_list, key=lambda x: str(x[key]))
        
        low = 0
        high = len(sorted_data) - 1
        results = []
        
        # Standard Binary Search to find *one* occurrence
        idx = -1
        while low <= high:
            mid = (low + high) // 2
            mid_val = str(sorted_data[mid][key]).lower()
            val = str(value).lower()
            
            if mid_val.startswith(val):
                idx = mid
                break 
            elif mid_val < val:
                low = mid + 1
            else:
                high = mid - 1
        
        if idx != -1:
            # Expand left
            i = idx
            while i >= 0 and str(sorted_data[i][key]).lower().startswith(str(value).lower()):
                if sorted_data[i] not in results: results.append(sorted_data[i])
                i -= 1
            # Expand right
            i = idx + 1
            while i < len(sorted_data) and str(sorted_data[i][key]).lower().startswith(str(value).lower()):
                if sorted_data[i] not in results: results.append(sorted_data[i])
                i += 1
                
        return results

# ==========================================
# 3. OOPS: USER HIERARCHY
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
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor = conn.execute("SELECT id, role, full_name FROM users WHERE username=? AND password_hash=?", (username, hashed))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            if row[1] == 'admin': return Admin(row[0], username)
            elif row[1] == 'pos': return POSOperator(row[0], username)
        return None

    def verify_password(self, password):
        conn = self.db.get_connection()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        res = conn.execute("SELECT id FROM users WHERE id=? AND password_hash=?", (self.user_id, hashed)).fetchone()
        conn.close()
        return res is not None

    def change_password(self, new_password):
        conn = self.db.get_connection()
        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, self.user_id))
        conn.commit()
        conn.close()

    @staticmethod
    def check_strength(password):
        score = 0
        if len(password) >= 8: score += 1
        if any(c.isupper() for c in password): score += 1
        if any(c.islower() for c in password): score += 1
        if any(c.isdigit() for c in password): score += 1
        if any(not c.isalnum() for c in password): score += 1
        return score

class Admin(User):
    def __init__(self, user_id, username):
        super().__init__(user_id, username, 'admin')

    def update_setting(self, key, value):
        conn = self.db.get_connection()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()

    def create_operator(self, fullname, username, password):
        conn = self.db.get_connection()
        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                         (fullname, username, hashed, 'pos'))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def manage_category(self, action, name, new_name=None):
        conn = self.db.get_connection()
        try:
            if action == 'add':
                conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            elif action == 'rename':
                conn.execute("UPDATE categories SET name=? WHERE name=?", (new_name, name))
            elif action == 'delete':
                # Safe Delete: Move products to Uncategorized first
                cat_id = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
                uncat_id = conn.execute("SELECT id FROM categories WHERE name='Uncategorized'").fetchone()
                
                if cat_id and uncat_id:
                    # Move products
                    conn.execute("UPDATE products SET category_id=? WHERE category_id=?", (uncat_id[0], cat_id[0]))
                    # Delete category
                    conn.execute("DELETE FROM categories WHERE id=?", (cat_id[0],))
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            conn.close()

class POSOperator(User):
    def __init__(self, user_id, username):
        super().__init__(user_id, username, 'pos')

    def process_order(self, customer_mobile, cart, payment_mode, gst_config):
        conn = self.db.get_connection()
        
        # Calculate totals
        total_selling = sum(item['selling_price'] * item['qty'] for item in cart.values())
        gst_amt = 0
        if gst_config['enabled']:
            gst_amt = total_selling * (gst_config['percent'] / 100)
        
        final_amt = total_selling + gst_amt
        order_id = f"INV{int(datetime.datetime.now().timestamp())}"

        # Insert Order
        conn.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode) 
                        VALUES (?, ?, ?, ?, ?, ?)''', 
                     (order_id, customer_mobile, self.username, final_amt, gst_amt, payment_mode))

        # Insert Items & Update Stock
        for pid, item in cart.items():
            conn.execute("INSERT INTO order_items (order_id, product_id, quantity, price, cost) VALUES (?, ?, ?, ?, ?)",
                         (order_id, pid, item['qty'], item['selling_price'], item['cost_price']))
            # Update stock and sales_count
            conn.execute("UPDATE products SET stock = stock - ?, sales_count = sales_count + ? WHERE id=?",
                         (item['qty'], item['qty'], pid))

        # Update Customer Stats
        conn.execute("UPDATE customers SET total_spent = total_spent + ?, total_visits = total_visits + 1 WHERE mobile=?",
                     (final_amt, customer_mobile))
        
        conn.commit()
        conn.close()
        return order_id, final_amt, gst_amt

# ==========================================
# 4. ANALYTICS ENGINE (EXPANDED)
# ==========================================
class AnalyticsEngine:
    def __init__(self):
        self.db = DatabaseManager()

    def get_sales_report(self, start_date, end_date):
        conn = self.db.get_connection()
        query = f"""
            SELECT date(timestamp) as date, SUM(total_amount) as sales, COUNT(order_id) as orders
            FROM orders 
            WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY date(timestamp)
        """
        return pd.read_sql_query(query, conn)

    def get_financials_extended(self, start_date, end_date):
        conn = self.db.get_connection()
        
        # 1. Revenue (Total Sales)
        rev_query = f"SELECT SUM(total_amount) FROM orders WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'"
        revenue = conn.execute(rev_query).fetchone()[0] or 0
        
        # 2. Total Orders
        ord_query = f"SELECT COUNT(*) FROM orders WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'"
        total_orders = conn.execute(ord_query).fetchone()[0] or 0
        
        # 3. Avg Order Value
        aov = revenue / total_orders if total_orders > 0 else 0

        # 4. Total Cost
        cost_query = f"""
            SELECT SUM(oi.cost * oi.quantity) 
            FROM order_items oi 
            JOIN orders o ON oi.order_id = o.order_id 
            WHERE o.status='active' AND date(o.timestamp) BETWEEN '{start_date}' AND '{end_date}'
        """
        total_cost = conn.execute(cost_query).fetchone()[0] or 0
        
        # 5. Gross Profit
        gross_profit = revenue - total_cost
        
        # 6. Gross Margin
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0

        # 8. Inventory Turnover (Simplified: Total Units Sold / Avg Stock approximation)
        # Using Total Sales Count from products table as a proxy for turnover velocity
        turnover_query = "SELECT SUM(sales_count) FROM products"
        turnover = conn.execute(turnover_query).fetchone()[0] or 0
        
        # 9. Customer Retention Rate
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        returning_cust = conn.execute("SELECT COUNT(*) FROM customers WHERE total_visits > 1").fetchone()[0]
        retention_rate = (returning_cust / total_customers * 100) if total_customers > 0 else 0

        conn.close()
        
        return {
            'revenue': revenue,
            'total_orders': total_orders,
            'aov': aov,
            'total_cost': total_cost,
            'gross_profit': gross_profit,
            'gross_margin': gross_margin,
            'inventory_turnover': turnover,
            'retention_rate': retention_rate
        }

    def get_product_profitability(self):
        # 7. Product-wise Profitability (Top 5)
        conn = self.db.get_connection()
        query = """
            SELECT name, (selling_price - cost_price) * sales_count as total_profit 
            FROM products 
            ORDER BY total_profit DESC 
            LIMIT 5
        """
        return pd.read_sql_query(query, conn)

    def predict_sales(self, df):
        # 10. Sales Forecast
        if len(df) < 2: return None, None
        
        df['idx'] = range(len(df))
        X = df['idx'].values
        y = df['sales'].values
        
        # Linear Regression: y = mx + c
        m, c = np.polyfit(X, y, 1)
        
        # Forecast
        future_X = np.arange(len(df), len(df) + 7)
        future_y = m * future_X + c
        
        return (X, m*X + c), (future_X, future_y)

# ==========================================
# 5. UTILITIES
# ==========================================
def generate_qr(upi_id, store_name, amount, note="Bill Payment"):
    # UPI URL Format
    payload = f"upi://pay?pa={upi_id}&pn={store_name}&am={amount}&cu=INR&tn={note}"
    qr = qrcode.make(payload)
    path = "temp_qr.png"
    qr.save(path)
    return path

def generate_pdf(invoice_data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, invoice_data['store_name'], ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, f"Inv: {invoice_data['id']}", ln=True, align='C')
    
    pdf.ln(10)
    pdf.cell(100, 10, f"Customer: {invoice_data['customer_name']}", 0, 1)
    pdf.cell(100, 10, f"Mobile: {invoice_data['customer_mobile']}", 0, 1)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(80, 10, "Item", 1)
    pdf.cell(30, 10, "Qty", 1)
    pdf.cell(40, 10, "Price", 1)
    pdf.cell(40, 10, "Total", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    for item in invoice_data['items']:
        pdf.cell(80, 10, item['name'], 1)
        pdf.cell(30, 10, str(item['qty']), 1)
        pdf.cell(40, 10, f"{item['selling_price']:.2f}", 1)
        pdf.cell(40, 10, f"{item['selling_price']*item['qty']:.2f}", 1)
        pdf.ln()
        
    pdf.ln(5)
    pdf.cell(150, 10, "GST", 0)
    pdf.cell(40, 10, f"{invoice_data['gst']:.2f}", 0, 1)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(150, 10, "Total", 0)
    pdf.cell(40, 10, f"{invoice_data['total']:.2f}", 0, 1)
    
    filename = f"{invoice_data['customer_name']}_{invoice_data['customer_mobile']}_{int(datetime.datetime.now().timestamp())}.pdf"
    pdf.output(filename)
    return filename
