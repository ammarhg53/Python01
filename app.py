import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import re
from backend import DatabaseManager, User, Admin, POSOperator, SearchAlgorithms, AnalyticsEngine, generate_qr, generate_pdf

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="SmartInventory Enterprise", layout="wide", page_icon="📦")
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; }
    .card { padding: 15px; border: 1px solid #ddd; border-radius: 10px; margin-bottom: 10px; background: white; text-align: center; }
    .stock-green { color: green; font-weight: bold; }
    .stock-red { color: red; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Session State Init
if 'user' not in st.session_state: st.session_state.user = None
if 'cart' not in st.session_state: st.session_state.cart = {} # Dictionary {pid: {details}}
if 'search_mode' not in st.session_state: st.session_state.search_mode = 'Linear'

# ==========================================
# AUTHENTICATION
# ==========================================
def login():
    st.title("📦 SmartInventory Enterprise")
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.info("### 🔐 Secure Login")
        st.markdown("**Admin:** `admin` / `Admin@123`")
        st.markdown("**POS:** `pos1` / `Pos@123`")
    
    with c2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.button("Login"):
            user = User.login(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials")

# ==========================================
# ADMIN PANEL
# ==========================================
def admin_panel():
    st.sidebar.header(f"👤 Admin: {st.session_state.user.username}")
    nav = st.sidebar.radio("Menu", ["Analytics", "Inventory", "Settings", "Profile", "Manage Operators"])
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()
        
    db = DatabaseManager()
    conn = db.get_connection()

    if nav == "Analytics":
        st.title("📈 Advanced Business Analytics")
        
        c1, c2 = st.columns(2)
        start_d = c1.date_input("From", value=pd.to_datetime("2026-01-01"))
        end_d = c2.date_input("To", value=pd.to_datetime("today"))
        
        engine = AnalyticsEngine()
        
        # 1. Financials
        rev, cost, profit, margin = engine.get_financials(start_d, end_d)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"₹{rev:,.2f}")
        m2.metric("Total Cost", f"₹{cost:,.2f}")
        m3.metric("Gross Profit", f"₹{profit:,.2f}", delta_color="normal")
        m4.metric("Gross Margin", f"{margin:.1f}%", delta=f"{margin:.1f}%")
        
        # 2. Decision Insights
        st.info("🧠 **AI Insights:**")
        if margin < 20: st.warning("⚠️ Low Gross Margin! Consider increasing prices or negotiating costs.")
        elif margin > 50: st.success("✅ Excellent Margin! Promote these products aggressively.")
        
        # 3. Regression
        st.markdown("### 📊 Sales Forecasting (Linear Regression)")
        sales_df = engine.get_sales_report(start_d, end_d)
        if not sales_df.empty:
            (X, y_fit), (fut_X, fut_y) = engine.predict_sales(sales_df)
            if X is not None:
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.scatter(sales_df['date'], sales_df['sales'], color='blue', label='Actual')
                ax.plot(sales_df['date'], y_fit, color='green', linestyle='--', label='Trend')
                ax.set_title(f"Sales Trend: {'Growing 📈' if y_fit[-1] > y_fit[0] else 'Declining 📉'}")
                ax.legend()
                st.pyplot(fig)
        else:
            st.warning("Not enough data for prediction")

    elif nav == "Inventory":
        st.title("📦 Inventory Manager")
        
        # Search Mode Toggle
        mode = st.radio("Search Algorithm", ["Linear Search (O(n))", "Binary Search (O(log n))"], horizontal=True)
        st.session_state.search_mode = "Binary" if "Binary" in mode else "Linear"
        
        search_q = st.text_input("Search Product")
        
        # Fetch Data
        df = pd.read_sql_query("SELECT * FROM products", conn)
        products = df.to_dict('records')
        
        if search_q:
            if st.session_state.search_mode == "Linear":
                results = SearchAlgorithms.linear_search(products, "name", search_q)
            else:
                results = SearchAlgorithms.binary_search(products, "name", search_q)
            st.dataframe(pd.DataFrame(results))
        else:
            st.dataframe(df)

        with st.expander("➕ Add Product"):
            name = st.text_input("Name")
            cost = st.number_input("Cost Price", 1.0)
            sell = st.number_input("Selling Price", 1.0)
            stock = st.number_input("Stock", 0)
            if st.button("Add"):
                conn.execute("INSERT INTO products (name, category_id, selling_price, cost_price, stock) VALUES (?, 1, ?, ?, ?)",
                             (name, sell, cost, stock))
                conn.commit()
                st.success("Added")
                st.rerun()

    elif nav == "Settings":
        st.title("⚙️ Store Settings")
        settings = pd.read_sql_query("SELECT * FROM settings", conn).set_index("key")['value'].to_dict()
        
        s_name = st.text_input("Store Name", settings.get("store_name", ""))
        upi = st.text_input("UPI ID", settings.get("upi_id", ""))
        gst_en = st.checkbox("Enable GST", settings.get("gst_enabled") == "True")
        gst_p = st.number_input("GST %", value=float(settings.get("gst_percent", 18)))
        
        if st.button("Save Settings"):
            st.session_state.user.update_setting("store_name", s_name)
            st.session_state.user.update_setting("upi_id", upi)
            st.session_state.user.update_setting("gst_enabled", str(gst_en))
            st.session_state.user.update_setting("gst_percent", str(gst_p))
            st.success("Settings Saved")

    elif nav == "Profile":
        profile_section()

    elif nav == "Manage Operators":
        st.title("👥 Create POS Operator")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        
        strength = User.check_strength(new_pass)
        st.progress(strength/5)
        if strength < 5:
            st.error("Password too weak. Requirements: 8+ chars, Upper, Lower, Digit, Special.")
        else:
            if st.button("Create Operator"):
                if st.session_state.user.create_operator("Operator", new_user, new_pass):
                    st.success("Operator Created")
                else:
                    st.error("Username exists")

# ==========================================
# POS PANEL
# ==========================================
def pos_panel():
    st.sidebar.header(f"🛒 POS: {st.session_state.user.username}")
    menu = st.sidebar.radio("Menu", ["Billing", "Profile"])
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.cart = {}
        st.rerun()

    db = DatabaseManager()
    conn = db.get_connection()
    
    settings = pd.read_sql_query("SELECT * FROM settings", conn).set_index("key")['value'].to_dict()

    if menu == "Billing":
        st.title("🛍️ New Transaction")
        
        # 1. Customer
        with st.container():
            c1, c2 = st.columns([1, 2])
            country = c1.selectbox("Country", ["India (+91)", "USA (+1)", "UAE (+971)", "UK (+44)"])
            mobile_input = c2.text_input("Mobile Number")
            
            # Validation
            valid_mobile = False
            if mobile_input:
                patterns = {
                    "India (+91)": r"^[6-9]\d{9}$",
                    "USA (+1)": r"^\d{10}$",
                    "UAE (+971)": r"^5\d{8}$",
                    "UK (+44)": r"^7\d{9}$"
                }
                if re.match(patterns[country], mobile_input):
                    valid_mobile = True
                    cust = conn.execute("SELECT name FROM customers WHERE mobile=?", (mobile_input,)).fetchone()
                    cust_name = cust[0] if cust else st.text_input("New Customer Name")
                    if not cust and cust_name and st.button("Register Customer"):
                        conn.execute("INSERT INTO customers (mobile, name) VALUES (?,?)", (mobile_input, cust_name))
                        conn.commit()
                        st.success("Registered")
                        st.rerun()
                else:
                    st.error("Invalid Mobile Number Format")

        col_prod, col_cart = st.columns([2, 1])
        
        # 2. Product Grid
        with col_prod:
            st.subheader("Products")
            search = st.text_input("Search Item")
            
            query = "SELECT * FROM products"
            if search: query += f" WHERE name LIKE '%{search}%'"
            products = pd.read_sql_query(query, conn).to_dict('records')
            
            # Grid Layout
            cols = st.columns(3)
            for idx, p in enumerate(products):
                with cols[idx % 3]:
                    st.markdown(f"""
                    <div class="card">
                        <b>{p['name']}</b><br>
                        ₹{p['selling_price']}<br>
                        <span class="{'stock-green' if p['stock']>0 else 'stock-red'}">
                            {'In Stock: ' + str(p['stock']) if p['stock']>0 else 'OUT OF STOCK'}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if p['stock'] > 0:
                        if st.button("Add 🛒", key=f"add_{p['id']}"):
                            if p['id'] in st.session_state.cart:
                                if st.session_state.cart[p['id']]['qty'] < p['stock']:
                                    st.session_state.cart[p['id']]['qty'] += 1
                                    st.toast(f"Added another {p['name']}")
                                else:
                                    st.toast("Max stock reached!")
                            else:
                                st.session_state.cart[p['id']] = p
                                st.session_state.cart[p['id']]['qty'] = 1
                                st.toast(f"Added {p['name']}")
                    else:
                        st.button("🚫", disabled=True, key=f"no_{p['id']}")

        # 3. Dynamic Cart
        with col_cart:
            st.subheader("Cart")
            if not st.session_state.cart:
                st.info("Empty")
            else:
                total_val = 0
                for pid, item in list(st.session_state.cart.items()):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.write(f"{item['name']} (x{item['qty']})")
                    c2.write(f"₹{item['selling_price'] * item['qty']:.2f}")
                    if c3.button("❌", key=f"del_{pid}"):
                        del st.session_state.cart[pid]
                        st.rerun()
                    total_val += item['selling_price'] * item['qty']
                
                gst_amt = 0
                if settings.get("gst_enabled") == "True":
                    gst_amt = total_val * (float(settings.get("gst_percent", 18)) / 100)
                
                final_total = total_val + gst_amt
                
                st.divider()
                st.write(f"Subtotal: ₹{total_val:.2f}")
                st.write(f"GST: ₹{gst_amt:.2f}")
                st.markdown(f"### Total: ₹{final_total:.2f}")
                
                # Payment
                pay_mode = st.radio("Payment Mode", ["Cash", "Card", "UPI"])
                
                if pay_mode == "Card":
                    st.text_input("Card No (16 digits)", max_chars=16)
                    c1, c2 = st.columns(2)
                    c1.text_input("Expiry (MM/YY)")
                    c2.text_input("CVV", max_chars=3, type="password")
                
                elif pay_mode == "UPI":
                    if final_total > 0:
                        qr_path = generate_qr(settings.get("upi_id"), settings.get("store_name"), final_total)
                        st.image(qr_path, caption="Scan to Pay", width=200)

                if st.button("✅ Complete Order", disabled=not valid_mobile or final_total==0):
                    gst_config = {'enabled': settings.get("gst_enabled")=="True", 'percent': float(settings.get("gst_percent", 18))}
                    
                    oid, tot, gst = st.session_state.user.process_order(mobile_input, st.session_state.cart, pay_mode, gst_config)
                    
                    st.success(f"Order {oid} Successful!")
                    
                    # Generate Invoice
                    inv_data = {
                        'id': oid, 'store_name': settings.get("store_name"),
                        'customer_name': cust_name, 'customer_mobile': mobile_input,
                        'items': st.session_state.cart.values(), 'gst': gst, 'total': tot
                    }
                    pdf_file = generate_pdf(inv_data)
                    with open(pdf_file, "rb") as f:
                        st.download_button("📄 Download Bill", f, file_name=pdf_file)
                    
                    st.session_state.cart = {} # Clear cart

    elif menu == "Profile":
        profile_section()

def profile_section():
    st.title("👤 My Profile")
    st.write(f"User: {st.session_state.user.username}")
    
    with st.expander("Change Password"):
        old = st.text_input("Old Password", type="password")
        new = st.text_input("New Password", type="password")
        
        if st.button("Update Password"):
            if st.session_state.user.verify_password(old):
                if User.check_strength(new) == 5:
                    st.session_state.user.change_password(new)
                    st.success("Password Updated")
                else:
                    st.error("New password is weak")
            else:
                st.error("Incorrect Old Password")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    if st.session_state.user:
        if st.session_state.user.role == 'admin':
            admin_panel()
        else:
            pos_panel()
    else:
        login()
