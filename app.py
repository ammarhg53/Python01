import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import time
from backend import DatabaseManager, User, Admin, POSOperator, AnalyticsEngine, check_password_strength, generate_invoice_pdf

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(page_title="SmartInventory Enterprise", layout="wide", page_icon="📦")
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    h1 { color: #2c3e50; }
    .stButton>button { width: 100%; border-radius: 5px; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if 'user' not in st.session_state:
    st.session_state.user = None
if 'cart' not in st.session_state:
    st.session_state.cart = []

# ==========================================
# AUTHENTICATION UI
# ==========================================
def login_page():
    st.title("🔐 SmartInventory Login")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### Demo Credentials")
        st.info("**Admin:** admin / Admin@123")
        st.info("**POS:** pos1 / Pos@123")
    
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            user = User.login(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid Username or Password")

# ==========================================
# ADMIN UI
# ==========================================
def admin_dashboard():
    st.sidebar.title(f"👤 Admin: {st.session_state.user.username}")
    menu = st.sidebar.radio("Navigation", ["Dashboard & Analytics", "Inventory", "Manage Orders", "Settings", "My Profile"])
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    db = DatabaseManager()
    conn = db.get_connection()

    if menu == "Dashboard & Analytics":
        st.title("📈 Business Analytics")
        
        # Date Range Filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=pd.to_datetime("2026-01-01"))
        with col2:
            end_date = st.date_input("End Date", value=pd.to_datetime("2026-02-09"))

        # Analytics Engine
        engine = AnalyticsEngine()
        sales_df = engine.get_sales_data(start_date, end_date)
        
        # KPI Cards
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        total_rev = sales_df['sales'].sum() if not sales_df.empty else 0
        total_orders = sales_df['orders'].sum() if not sales_df.empty else 0
        aov = total_rev / total_orders if total_orders > 0 else 0
        retention = engine.get_retention_rate()
        
        kpi1.metric("Total Revenue", f"₹{total_rev:,.2f}")
        kpi2.metric("Total Orders", total_orders)
        kpi3.metric("Avg Order Value", f"₹{aov:,.2f}")
        kpi4.metric("Retention Rate", f"{retention:.1f}%")

        # Linear Regression (Sales Forecasting)
        st.markdown("### 📊 Sales Trend & Forecast (Linear Regression)")
        if not sales_df.empty:
            (X, y_fit), (future_X, future_y) = engine.get_linear_regression(sales_df)
            
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.scatter(sales_df['date'], sales_df['sales'], color='blue', label='Actual Sales')
            ax.plot(sales_df['date'], y_fit, color='green', linestyle='--', label='Trend Line')
            
            # Show Forecast in text
            st.info(f"Predicted Sales for next 7 days show a trend slope of: {y_fit[-1] - y_fit[0]:.2f}")
            ax.legend()
            st.pyplot(fig)
        else:
            st.warning("No data for selected range.")

        # Inventory Analysis
        st.markdown("### 📦 Category Performance")
        cat_df = engine.get_category_sales()
        if not cat_df.empty:
            st.bar_chart(cat_df.set_index('name')['revenue'])

    elif menu == "Inventory":
        st.title("📦 Inventory Management")
        
        tab1, tab2 = st.tabs(["View Products", "Add Product"])
        
        with tab1:
            search_term = st.text_input("🔍 Search Product (Linear Search O(n))")
            df = pd.read_sql_query("SELECT p.id, p.name, c.name as category, p.stock, p.selling_price FROM products p JOIN categories c ON p.category_id = c.id", conn)
            
            if search_term:
                # O(n) Linear Search simulation
                df = df[df['name'].str.contains(search_term, case=False)]
            
            st.dataframe(df, use_container_width=True)
            
            # Low Stock Alert
            low_stock = df[df['stock'] < 10]
            if not low_stock.empty:
                st.error(f"⚠️ {len(low_stock)} products are low on stock!")

        with tab2:
            st.markdown("#### Add New Product")
            name = st.text_input("Product Name")
            cats = pd.read_sql_query("SELECT * FROM categories", conn)
            cat_id = st.selectbox("Category", cats['id'], format_func=lambda x: cats[cats['id']==x]['name'].values[0])
            price = st.number_input("Selling Price", min_value=1.0)
            cost = st.number_input("Cost Price", min_value=1.0)
            stock = st.number_input("Initial Stock", min_value=1)
            
            if st.button("Add Product"):
                st.session_state.user.add_product(name, cat_id, price, cost, stock, "")
                st.success("Product Added Successfully!")

    elif menu == "Manage Orders":
        st.title("📋 Order Management")
        orders = pd.read_sql_query("SELECT * FROM orders ORDER BY timestamp DESC", conn)
        st.dataframe(orders)
        
        st.markdown("### ❌ Cancel Order")
        oid = st.text_input("Order ID to Cancel")
        reason = st.text_input("Reason")
        pwd = st.text_input("Admin Password to confirm", type="password")
        
        if st.button("Cancel Order"):
            # Verify password again
            hashed = hashlib.sha256(pwd.encode()).hexdigest()
            cursor = conn.execute("SELECT * FROM users WHERE id=? AND password_hash=?", (st.session_state.user.user_id, hashed))
            if cursor.fetchone():
                st.session_state.user.cancel_order(oid, reason)
                st.success("Order Cancelled")
                st.rerun()
            else:
                st.error("Incorrect Password")

    elif menu == "My Profile":
        profile_section()

# ==========================================
# POS UI
# ==========================================
def pos_dashboard():
    st.sidebar.title(f"🛒 POS: {st.session_state.user.username}")
    menu = st.sidebar.radio("Navigation", ["Billing", "My Profile"])
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.cart = []
        st.rerun()

    db = DatabaseManager()
    conn = db.get_connection()

    if menu == "Billing":
        st.title("🛍️ New Bill")
        
        # 1. Customer Details
        with st.expander("👤 Customer Details", expanded=True):
            mobile = st.text_input("Mobile Number (+91/USA/UK)", max_chars=15)
            if mobile:
                cust = conn.execute("SELECT * FROM customers WHERE mobile=?", (mobile,)).fetchone()
                if cust:
                    st.success(f"Welcome back, {cust[1]}! (Visits: {cust[4]})")
                    c_name = cust[1]
                else:
                    st.warning("New Customer")
                    c_name = st.text_input("Customer Name")
                    if st.button("Register Customer"):
                        conn.execute("INSERT INTO customers (mobile, name) VALUES (?,?)", (mobile, c_name))
                        conn.commit()
                        st.rerun()
        
        # 2. Product Selection
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🔍 Select Products")
            search = st.text_input("Search Product")
            query = "SELECT * FROM products WHERE stock > 0"
            if search:
                query += f" AND name LIKE '%{search}%'"
            
            products = pd.read_sql_query(query, conn)
            
            for _, row in products.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.markdown(f"**{row['name']}** (₹{row['selling_price']})")
                    c1.caption(f"Stock: {row['stock']}")
                    qty = c2.number_input("Qty", min_value=1, max_value=row['stock'], key=f"q_{row['id']}")
                    if c3.button("Add", key=f"add_{row['id']}"):
                        # Add to cart session
                        item = {
                            "id": row['id'], 
                            "name": row['name'], 
                            "price": row['selling_price'], 
                            "cost": row['cost_price'],
                            "qty": qty
                        }
                        st.session_state.cart.append(item)
                        st.success(f"Added {row['name']}")

        # 3. Cart & Payment
        with col2:
            st.markdown("### 🛒 Cart")
            if not st.session_state.cart:
                st.info("Cart is empty")
            else:
                cart_df = pd.DataFrame(st.session_state.cart)
                st.dataframe(cart_df[['name', 'qty', 'price']], hide_index=True)
                
                total = sum(x['price'] * x['qty'] for x in st.session_state.cart)
                
                # GST Calculation
                gst_conf = conn.execute("SELECT value FROM settings WHERE key='gst_percent'").fetchone()[0]
                gst_en = conn.execute("SELECT value FROM settings WHERE key='gst_enabled'").fetchone()[0]
                
                gst_amt = 0
                if gst_en == 'True':
                    gst_amt = total * (float(gst_conf) / 100)
                
                grand_total = total + gst_amt
                
                st.divider()
                st.markdown(f"**Subtotal:** ₹{total:.2f}")
                st.markdown(f"**GST ({gst_conf}%):** ₹{gst_amt:.2f}")
                st.markdown(f"### Total: ₹{grand_total:.2f}")
                
                if st.button("Clear Cart"):
                    st.session_state.cart = []
                    st.rerun()
                
                st.divider()
                st.markdown("### 💰 Payment")
                pay_mode = st.radio("Mode", ["CASH", "UPI", "CARD"])
                
                if pay_mode == "CARD":
                    st.text_input("Card Number (16 digit)")
                    st.text_input("CVV")
                
                if st.button("✅ Place Order"):
                    if not mobile or not c_name:
                        st.error("Customer details required")
                    else:
                        gst_config = {'enabled': gst_en=='True', 'percent': float(gst_conf)}
                        oid, tot, gst = st.session_state.user.create_order(mobile, st.session_state.cart, pay_mode, gst_config)
                        
                        st.success(f"Order Placed! ID: {oid}")
                        
                        # Generate PDF
                        pdf_file = generate_invoice_pdf(
                            "SmartInventory Store", oid, 
                            {'name': c_name, 'mobile': mobile}, 
                            st.session_state.cart, tot, gst, st.session_state.user.username
                        )
                        
                        with open(pdf_file, "rb") as f:
                            st.download_button("📄 Download Invoice", f, file_name=pdf_file)
                        
                        st.session_state.cart = []
                        # Cleanup pdf
                        # os.remove(pdf_file) 

    elif menu == "My Profile":
        profile_section()

def profile_section():
    st.title("👤 My Profile")
    st.markdown(f"**Username:** {st.session_state.user.username}")
    st.markdown(f"**Role:** {st.session_state.user.role}")
    
    st.divider()
    st.markdown("### 🔐 Change Password")
    
    new_pass = st.text_input("New Password", type="password")
    
    # Password Strength Meter
    if new_pass:
        score = check_password_strength(new_pass)
        st.progress(score / 5)
        if score < 5:
            st.error("Weak Password! Must be 8+ chars, Upper, Lower, Digit, Special.")
        else:
            st.success("Strong Password ✅")
            if st.button("Update Password"):
                st.session_state.user.change_password(new_pass)
                st.success("Password Updated!")

# ==========================================
# MAIN ROUTER
# ==========================================
if __name__ == "__main__":
    if st.session_state.user is None:
        login_page()
    else:
        if st.session_state.user.role == 'admin':
            admin_dashboard()
        else:
            pos_dashboard()
