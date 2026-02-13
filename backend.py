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
        
        # Check if we need to reset (Bad data detection or Missing Users)
        needs_reset = False
        try:
            # Check for tables existence
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
            if not cursor.fetchone():
                needs_reset = True
            else:
                # 1. Check if Users exist (CRITICAL FIX for Auth)
                cursor.execute("SELECT count(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    needs_reset = True

                # 2. Check for bad product names
                if not needs_reset:
                    cursor.execute("SELECT count(*) FROM products WHERE name LIKE 'Item%' OR name LIKE 'Product%'")
                    if cursor.fetchone()[0] > 0:
                        needs_reset = True
                
                # 3. Check for incomplete categories
                if not needs_reset:
                    cursor.execute("SELECT count(*) FROM categories")
                    if cursor.fetchone()[0] < 5: 
                        needs_reset = True
        except sqlite3.Error:
            needs_reset = True

        if needs_reset:
            self.reset_database(conn)
        else:
            self.create_tables(conn)
            
        conn.close()

    def reset_database(self, conn):
        """Drops all tables and rebuilds them with fresh, clean seed data."""
        cursor = conn.cursor()
        
        # Disable foreign keys temporarily to drop tables safely
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        tables = ['order_items', 'orders', 'products', 'categories', 'customers', 'users', 'settings']
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        
        # Re-enable foreign keys and recreate tables
        cursor.execute("PRAGMA foreign_keys = ON")
        self.create_tables(conn)
        
        # Seed data with fresh cursor
        cursor = conn.cursor()
        self.seed_data(cursor, conn)

    def create_tables(self, conn):
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

    def seed_data(self, cursor, conn):
        """Strict clean seeding with realistic data."""
        if isinstance(cursor, sqlite3.Connection):
             conn = cursor
             cursor = conn.cursor()

        # 1. Users (Ensure Demo Credentials)
        # Using SHA-256 as required
        admin_pass = hashlib.sha256("Admin@123".encode()).hexdigest()
        pos_pass = hashlib.sha256("Pos@123".encode()).hexdigest()
        
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("System Admin", "admin", admin_pass, "admin"))
        cursor.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                       ("POS Operator 1", "pos1", pos_pass, "pos"))
        
        # 2. Categories
        categories = ['Snacks', 'Beverages', 'Grocery', 'Dairy', 'Bakery', 
                      'Frozen', 'Personal Care', 'Stationery', 'Electronics', 'Household']
        cat_map = {}
        for cat in categories:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (cat,))
            cat_map[cat] = cursor.lastrowid
        
        # 3. Products (Realistic Names ONLY)
        products_data = {
            'Snacks': [('Lays Classic Salted', 20, 15), ('Doritos Nacho Cheese', 30, 22), ('Pringles Sour Cream', 110, 85), ('Kurkure Masala Munch', 20, 14), ('Haldirams Bhujia', 45, 35)],
            'Beverages': [('Coca Cola 750ml', 45, 35), ('Pepsi 500ml', 40, 30), ('Red Bull Energy Drink', 125, 95), ('Tropicana Mixed Fruit', 110, 80), ('Kinley Water 1L', 20, 12)],
            'Grocery': [('India Gate Basmati Rice 1kg', 120, 95), ('Tata Salt 1kg', 25, 18), ('Aashirvaad Atta 5kg', 240, 210), ('Toor Dal 1kg', 160, 130), ('Fortune Oil 1L', 145, 125)],
            'Dairy': [('Amul Butter 100g', 56, 48), ('Mother Dairy Milk 1L', 66, 60), ('Paneer 200g', 85, 70), ('Amul Cheese Slices', 140, 115), ('Curd 400g', 40, 32)],
            'Bakery': [('Britannia White Bread', 45, 38), ('Chocolate Muffin', 60, 40), ('Butter Croissant', 80, 50), ('Fruit Cake', 150, 110)],
            'Frozen': [('McCain French Fries 400g', 125, 95), ('Safal Green Peas 500g', 60, 45), ('Amul Vanilla Ice Cream 1L', 150, 115)],
            'Personal Care': [('Dove Shampoo 180ml', 160, 120), ('Colgate Toothpaste', 90, 70), ('Nivea Body Lotion', 250, 190), ('Dettol Handwash', 85, 65)],
            'Stationery': [('Classmate Notebook A4', 60, 40), ('Parker Pen Vector', 250, 180), ('Fevicol 100g', 50, 35), ('A4 Paper Bundle', 300, 240)],
            'Electronics': [('USB C Cable 1m', 350, 150), ('Wireless Mouse Logitech', 600, 400), ('Sony Earphones', 800, 550), ('SanDisk 32GB Pen Drive', 450, 300)],
            'Household': [('Vim Dishwash Gel 500ml', 110, 90), ('Surf Excel 1kg', 140, 120), ('Harpic Toilet Cleaner', 180, 150), ('Duracell AA Batteries (4)', 160, 110)]
        }

        all_products = [] # List of (id, selling_price, cost_price)

        for cat, items in products_data.items():
            cid = cat_map[cat]
            for name, sell, cost in items:
                stock = random.randint(20, 100)
                # Sales count starts at 0, updated by order seeding
                cursor.execute('''INSERT INTO products (name, category_id, selling_price, cost_price, stock, sales_count) 
                                  VALUES (?, ?, ?, ?, ?, 0)''',
                               (name, cid, float(sell), float(cost), stock))
                all_products.append({'id': cursor.lastrowid, 'sell': float(sell), 'cost': float(cost)})

        # 4. Customers (50 records)
        customer_mobiles = []
        for i in range(1, 51):
            mobile = f"98765432{i:02d}"
            cursor.execute("INSERT INTO customers (mobile, name, total_spent, total_visits) VALUES (?, ?, ?, ?)", 
                           (mobile, f"Customer {i}", 0, 0))
            customer_mobiles.append(mobile)

        # 5. Settings
        settings = {
            'store_name': 'SmartInventory Enterprise',
            'gst_enabled': 'True',
            'gst_percent': '18',
            'upi_id': 'merchant@okaxis'
        }
        for k, v in settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # 6. Orders (History for Analytics - Past 60 days, 50 orders)
        base_date = datetime.datetime.now()
        payment_modes = ['CASH', 'UPI', 'CARD', 'UPI', 'CASH']
        
        for i in range(50): 
            # Randomize date
            days_ago = random.randint(0, 60)
            hour = random.choice([10, 11, 14, 15, 16, 17, 18, 18, 19, 19, 20])
            minute = random.randint(0, 59)
            order_date = (base_date - datetime.timedelta(days=days_ago)).replace(hour=hour, minute=minute)
            
            order_id = f"ORD{random.randint(10000,99999)}"
            cust_mobile = random.choice(customer_mobiles)
            pay_mode = random.choice(payment_modes)
            
            # Select random items for this order
            num_items = random.randint(1, 4)
            selected_items = random.sample(all_products, num_items)
            
            total_sell = 0
            gst_rate = 0.18
            
            # 15% Cancellation Rate
            status = 'active'
            reason = None
            if random.random() < 0.15:
                status = 'cancelled'
                reason = "Customer changed mind"

            # Prepare Order Items (Calculate Total FIRST)
            # CRITICAL FIX: Do NOT insert into order_items before orders
            current_order_items = []
            for item in selected_items:
                qty = random.randint(1, 3)
                price = item['sell']
                cost = item['cost']
                total_sell += price * qty
                current_order_items.append((item, qty, price, cost))

            total_amount = total_sell * (1 + gst_rate)
            gst_amount = total_sell * gst_rate
            
            # 1. Insert ORDER First (Parent)
            cursor.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode, timestamp, status, cancellation_reason)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (order_id, cust_mobile, "pos1", total_amount, gst_amount, pay_mode, order_date, status, reason))
            
            # 2. Insert Order Items (Children) & Update Stock
            for item, qty, price, cost in current_order_items:
                cursor.execute("INSERT INTO order_items (order_id, product_id, quantity, price, cost) VALUES (?, ?, ?, ?, ?)",
                               (order_id, item['id'], qty, price, cost))
                
                # Update product stock/sales only if active
                if status == 'active':
                    cursor.execute("UPDATE products SET stock = stock - ?, sales_count = sales_count + ? WHERE id=?", 
                                   (qty, qty, item['id']))
            
            # 3. Update Customer Stats
            if status == 'active':
                cursor.execute("UPDATE customers SET total_spent = total_spent + ?, total_visits = total_visits + 1 WHERE mobile=?", (total_amount, cust_mobile))
            else:
                cursor.execute("UPDATE customers SET cancelled_orders = cancelled_orders + 1 WHERE mobile=?", (cust_mobile,))

        conn.commit()

# ==========================================
# 2. ALGORITHMS
# ==========================================
class SearchAlgorithms:
    @staticmethod
    def linear_search(data_list, key, value):
        results = []
        for item in data_list:
            if str(item[key]).lower().startswith(str(value).lower()):
                results.append(item)
        return results

    @staticmethod
    def binary_search(data_list, key, value):
        sorted_data = sorted(data_list, key=lambda x: str(x[key]))
        low = 0
        high = len(sorted_data) - 1
        results = []
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
            i = idx
            while i >= 0 and str(sorted_data[i][key]).lower().startswith(str(value).lower()):
                if sorted_data[i] not in results: results.append(sorted_data[i])
                i -= 1
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
        # 1. Input Validation
        username = username.strip() if username else ""
        if not username or not password:
            return None, "Username and password cannot be empty"

        db = DatabaseManager()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 2. Username Check (Strict Case-Sensitive)
        cursor.execute("SELECT id, role, full_name, password_hash, username FROM users WHERE username=?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None, "User does not exist"
        
        db_username = row[4]
        if db_username != username:
            return None, "User does not exist"
        
        # 3. Password Check
        stored_hash = row[3]
        input_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if input_hash == stored_hash:
            if row[1] == 'admin': 
                return Admin(row[0], username), "Login successful"
            elif row[1] == 'pos': 
                return POSOperator(row[0], username), "Login successful"
        
        return None, "Incorrect password"

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
            if not name or not name.strip(): return False
            if action == 'add':
                conn.execute("INSERT INTO categories (name) VALUES (?)", (name.strip(),))
            elif action == 'rename':
                if not new_name or not new_name.strip(): return False
                conn.execute("UPDATE categories SET name=? WHERE name=?", (new_name.strip(), name))
            conn.commit()
            return True
        except Exception as e:
            return False
        finally:
            conn.close()

    def restock_product(self, product_id, qty):
        if qty <= 0: return False
        conn = self.db.get_connection()
        try:
            conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (qty, product_id))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def cancel_order(self, order_id, reason, password_check):
        # 1. Verify Password
        if not self.verify_password(password_check):
            return False, "Invalid Password"
        
        conn = self.db.get_connection()
        try:
            # 2. Check if already cancelled
            curr_status = conn.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if not curr_status or curr_status[0] == 'cancelled':
                return False, "Order already cancelled or not found"

            # 3. Update Status
            conn.execute("UPDATE orders SET status='cancelled', cancellation_reason=? WHERE order_id=?", (reason, order_id))
            
            # 4. Update Customer Stats
            order_data = conn.execute("SELECT customer_mobile, total_amount FROM orders WHERE order_id=?", (order_id,)).fetchone()
            if order_data:
                mob, amt = order_data
                conn.execute("UPDATE customers SET total_spent = total_spent - ?, total_visits = total_visits - 1, cancelled_orders = cancelled_orders + 1 WHERE mobile=?", (amt, mob))
            
            conn.commit()
            return True, "Order Cancelled Successfully"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

class POSOperator(User):
    def __init__(self, user_id, username):
        super().__init__(user_id, username, 'pos')

    def process_order(self, customer_mobile, cart, payment_mode, gst_config):
        conn = self.db.get_connection()
        total_selling = sum(item['selling_price'] * item['qty'] for item in cart.values())
        gst_amt = 0
        if gst_config['enabled']:
            gst_amt = total_selling * (gst_config['percent'] / 100)
        final_amt = total_selling + gst_amt
        order_id = f"INV{int(datetime.datetime.now().timestamp())}"

        conn.execute('''INSERT INTO orders (order_id, customer_mobile, operator_username, total_amount, gst_amount, payment_mode) 
                        VALUES (?, ?, ?, ?, ?, ?)''', 
                     (order_id, customer_mobile, self.username, final_amt, gst_amt, payment_mode))

        for pid, item in cart.items():
            conn.execute("INSERT INTO order_items (order_id, product_id, quantity, price, cost) VALUES (?, ?, ?, ?, ?)",
                         (order_id, pid, item['qty'], item['selling_price'], item['cost_price']))
            conn.execute("UPDATE products SET stock = stock - ?, sales_count = sales_count + ? WHERE id=?",
                         (item['qty'], item['qty'], pid))

        conn.execute("UPDATE customers SET total_spent = total_spent + ?, total_visits = total_visits + 1 WHERE mobile=?",
                     (final_amt, customer_mobile))
        conn.commit()
        conn.close()
        return order_id, final_amt, gst_amt

# ==========================================
# 4. ANALYTICS ENGINE
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
        
        rev_query = f"SELECT SUM(total_amount) FROM orders WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'"
        revenue = conn.execute(rev_query).fetchone()[0] or 0
        
        ord_query = f"SELECT COUNT(*) FROM orders WHERE status='active' AND date(timestamp) BETWEEN '{start_date}' AND '{end_date}'"
        total_orders = conn.execute(ord_query).fetchone()[0] or 0
        
        aov = revenue / total_orders if total_orders > 0 else 0

        cost_query = f"""
            SELECT SUM(oi.cost * oi.quantity) 
            FROM order_items oi 
            JOIN orders o ON oi.order_id = o.order_id 
            WHERE o.status='active' AND date(o.timestamp) BETWEEN '{start_date}' AND '{end_date}'
        """
        total_cost = conn.execute(cost_query).fetchone()[0] or 0
        
        gross_profit = revenue - total_cost
        gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0

        turnover_query = "SELECT SUM(sales_count) FROM products"
        turnover = conn.execute(turnover_query).fetchone()[0] or 0
        
        total_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        returning_cust = conn.execute("SELECT COUNT(*) FROM customers WHERE total_visits > 1").fetchone()[0]
        retention_rate = (returning_cust / total_customers * 100) if total_customers > 0 else 0

        conn.close()
        return {
            'revenue': revenue, 'total_orders': total_orders, 'aov': aov,
            'total_cost': total_cost, 'gross_profit': gross_profit, 'gross_margin': gross_margin,
            'inventory_turnover': turnover, 'retention_rate': retention_rate
        }

    def get_top_selling_products(self):
        conn = self.db.get_connection()
        query = "SELECT name, sales_count FROM products ORDER BY sales_count DESC LIMIT 5"
        return pd.read_sql_query(query, conn)

    def get_category_analytics(self):
        conn = self.db.get_connection()
        query = """
            SELECT c.name, SUM(p.sales_count) as total_sold 
            FROM products p 
            JOIN categories c ON p.category_id = c.id 
            GROUP BY c.name
        """
        return pd.read_sql_query(query, conn)

    def get_payment_patterns(self):
        conn = self.db.get_connection()
        query = "SELECT payment_mode, COUNT(*) as count, SUM(total_amount) as volume FROM orders WHERE status='active' GROUP BY payment_mode"
        return pd.read_sql_query(query, conn)

    def get_hourly_trends(self):
        conn = self.db.get_connection()
        query = """
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as orders 
            FROM orders WHERE status='active' 
            GROUP BY hour ORDER BY hour
        """
        return pd.read_sql_query(query, conn)
    
    def get_daily_trends(self):
        conn = self.db.get_connection()
        query = """
            SELECT 
                CASE cast(strftime('%w', timestamp) as integer)
                    WHEN 0 THEN 'Sunday'
                    WHEN 1 THEN 'Monday'
                    WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday'
                    WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday'
                    WHEN 6 THEN 'Saturday'
                END as day_name, 
                COUNT(*) as orders 
            FROM orders WHERE status='active' 
            GROUP BY day_name 
            ORDER BY strftime('%w', timestamp)
        """
        return pd.read_sql_query(query, conn)

    def predict_sales(self, df, mode='Linear'):
        if len(df) < 2: return None, None
        
        df['idx'] = range(len(df))
        X = df['idx'].values
        y = df['sales'].values
        
        degree = 1 if mode == 'Linear' else 3
        
        coeffs = np.polyfit(X, y, degree)
        poly = np.poly1d(coeffs)
        
        future_X = np.arange(len(df), len(df) + 7)
        future_y = poly(future_X)
        
        return (X, poly(X)), (future_X, future_y)

# ==========================================
# 5. UTILITIES
# ==========================================
def generate_qr(upi_id, store_name, amount, note="Bill Payment"):
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
