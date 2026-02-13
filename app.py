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
    .card { padding: 15px; border: 1px solid #ddd; border-radius: 10px; margin-bottom: 10px; background: white; text-align: center; height: 100%; }
    .stock-green { color: green; font-weight: bold; }
    .stock-red { color: red; font-weight: bold; }
    .big-font { font-size: 18px !important; }
</style>
""", unsafe_allow_html=True)

# Session State Init
if 'user' not in st.session_state: st.session_state.user = None
if 'cart' not in st.session_state: st.session_state.cart = {} # Dictionary {pid: {details}}
if 'search_mode' not in st.session_state: st.session_state.search_mode = 'Linear'
if 'prod_page' not in st.session_state: st.session_state.prod_page = 0

ITEMS_PER_PAGE = 12

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
        st.title("📈 Advanced Business Analytics (10 Metrics)")
        
        c1, c2 = st.columns(2)
        start_d = c1.date_input("From", value=pd.to_datetime("2026-01-01"))
        end_d = c2.date_input("To", value=pd.to_datetime("today"))
        
        engine = AnalyticsEngine()
        data = engine.get_financials_extended(start_d, end_d)
        
        # Row 1
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("1. Total Revenue", f"₹{data['revenue']:,.0f}")
        m2.metric("2. Total Orders", data['total_orders'])
        m3.metric("3. Avg Order Value", f"₹{data['aov']:,.0f}")
        m4.metric("4. Total Cost", f"₹{data['total_cost']:,.0f}")
        m5.metric("5. Gross Profit", f"₹{data['gross_profit']:,.0f}", delta_color="normal")
        
        # Row 2
        m6, m7, m8, m9 = st.columns(4)
        m6.metric("6. Gross Margin", f"{data['gross_margin']:.1f}%", delta=f"{data['gross_margin']:.1f}%")
        m7.metric("7. Total Items Sold (Volume)", f"{data['inventory_turnover']:,}")
        m8.metric("8. Inventory Turnover Ratio", f"{(data['inventory_turnover']/500):.2f}x") # Approx
        m9.metric("9. Cust. Retention Rate", f"{data['retention_rate']:.1f}%")

        st.divider()
        
        col_charts1, col_charts2 = st.columns(2)
        
        with col_charts1:
            st.markdown("### 10. Sales Forecast (Linear Regression)")
            sales_df = engine.get_sales_report(start_d, end_d)
            if not sales_df.empty:
                (X, y_fit), (fut_X, fut_y) = engine.predict_sales(sales_df)
                if X is not None:
                    fig, ax = plt.subplots(figsize=(8, 4))
                    ax.scatter(sales_df['date'], sales_df['sales'], color='blue', label='Actual Sales')
                    ax.plot(sales_df['date'], y_fit, color='green', linestyle='--', label='Trend Line')
                    
                    trend = "Growing 📈" if y_fit[-1] > y_fit[0] else "Declining 📉"
                    ax.set_title(f"Sales Trend: {trend}")
                    plt.xticks(rotation=45) # Fix label visibility
                    ax.legend()
                    st.pyplot(fig)
            else:
                st.warning("Not enough data for prediction")

        with col_charts2:
            st.markdown("### Product Profitability (Top 5)")
            prof_df = engine.get_product_profitability()
            st.bar_chart(prof_df.set_index('name')['total_profit'])

    elif nav == "Inventory":
        st.title("📦 Inventory Manager")
        
        tab1, tab2, tab3, tab4 = st.tabs(["View Products", "Add Product", "Restock", "Manage Categories"])
        
        with tab1:
            search_q = st.text_input("Search Product")
            df = pd.read_sql_query("SELECT p.id, p.name, c.name as category, p.stock, p.selling_price FROM products p JOIN categories c ON p.category_id=c.id", conn)
            
            if search_q:
                # Demonstration of Algo Choice even in Admin
                df = df[df['name'].str.contains(search_q, case=False)]
            
            st.dataframe(df, use_container_width=True)

        with tab2:
            st.markdown("#### Add New Product")
            name = st.text_input("Name")
            cats = pd.read_sql_query("SELECT * FROM categories", conn)
            cat_id = st.selectbox("Category", cats['id'], format_func=lambda x: cats[cats['id']==x]['name'].values[0])
            cost = st.number_input("Cost Price", 0.0)
            sell = st.number_input("Selling Price", 0.0)
            stock = st.number_input("Initial Stock", 0)
            
            if st.button("Add Product"):
                if not name.strip():
                    st.error("Product name cannot be empty")
                elif cost <= 0 or sell <= 0:
                    st.error("Price must be greater than 0")
                elif stock < 0:
                    st.error("Stock cannot be negative")
                else:
                    # Default icon for all products
                    default_img = "https://img.icons8.com/color/150/box--v1.png"
                    conn.execute("INSERT INTO products (name, category_id, selling_price, cost_price, stock, sales_count, image_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (name.strip(), cat_id, sell, cost, stock, 0, default_img))
                    conn.commit()
                    st.success("Added")

        with tab3:
            st.markdown("#### Restock Inventory")
            prods = pd.read_sql_query("SELECT id, name, stock FROM products", conn)
            pid = st.selectbox("Select Product", prods['id'], format_func=lambda x: f"{prods[prods['id']==x]['name'].values[0]} (Curr: {prods[prods['id']==x]['stock'].values[0]})")
            qty = st.number_input("Quantity to Add", min_value=1, value=1)
            
            if st.button("Update Stock"):
                if st.session_state.user.restock_product(pid, qty):
                    st.success("Stock Updated Successfully")
                    st.rerun()
                else:
                    st.error("Failed to update stock")

        with tab4:
            st.markdown("#### Category Management")
            cats = pd.read_sql_query("SELECT * FROM categories", conn)
            
            c1, c2 = st.columns(2)
            with c1:
                new_cat = st.text_input("New Category Name")
                if st.button("Add Category"):
                    if not new_cat.strip():
                        st.error("Category name cannot be empty")
                    else:
                        if st.session_state.user.manage_category('add', new_cat):
                            st.success("Category Added")
                            st.rerun()
                        else:
                            st.error("Error adding category (might already exist)")
            
            with c2:
                target_cat = st.selectbox("Select Category to Rename", cats['name'])
                if target_cat != 'Uncategorized':
                    rename_val = st.text_input("Rename to")
                    if st.button("Rename"):
                        if not rename_val.strip():
                            st.error("New name cannot be empty")
                        else:
                            if st.session_state.user.manage_category('rename', target_cat, rename_val):
                                st.success("Renamed Successfully")
                                st.rerun()
                            else:
                                st.error("Rename failed")
                else:
                    st.info("Uncategorized cannot be modified")

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
            cust_name = ""
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
        
        # 2. Product Grid with Search & Pagination
        with col_prod:
            st.subheader("Products")
            
            # Search Algo Selection
            algo_choice = st.radio("Search Algorithm", ["Linear Search (O(n))", "Binary Search (O(log n))"], horizontal=True)
            if "Linear" in algo_choice:
                st.caption("ℹ️ Checks items one-by-one. Best for unsorted/small data.")
                st.session_state.search_mode = "Linear"
            else:
                st.caption("ℹ️ Divides sorted data halves. Best for large/sorted data.")
                st.session_state.search_mode = "Binary"

            search = st.text_input("Search Item")
            
            # Fetch all products first
            all_products = pd.read_sql_query("SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id=c.id", conn).to_dict('records')
            
            # Apply Search
            if search:
                if st.session_state.search_mode == "Linear":
                    filtered_products = SearchAlgorithms.linear_search(all_products, "name", search)
                else:
                    filtered_products = SearchAlgorithms.binary_search(all_products, "name", search)
            else:
                filtered_products = all_products

            # Pagination Logic
            total_items = len(filtered_products)
            total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            
            # Navigation Controls
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if st.button("⬅️ Prev") and st.session_state.prod_page > 0:
                    st.session_state.prod_page -= 1
            with pc2:
                st.markdown(f"<div style='text-align: center'>Page {st.session_state.prod_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
            with pc3:
                if st.button("Next ➡️") and st.session_state.prod_page < total_pages - 1:
                    st.session_state.prod_page += 1

            # Slice Data
            start_idx = st.session_state.prod_page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            page_items = filtered_products[start_idx:end_idx]
            
            # Grid Layout
            cols = st.columns(3)
            for idx, p in enumerate(page_items):
                with cols[idx % 3]:
                    # Use standard icon if image not available, but Seed uses specific URL.
                    # UI cleanup: removed Profit/Sales display as requested.
                    st.markdown(f"""
                    <div class="card">
                        <img src="{p['image_path']}" width="80" style="border-radius: 5px"><br>
                        <b>{p['name']}</b><br>
                        <span style="color: #666; font-size: 12px">{p['category_name']}</span><br>
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
                                    st.toast(f"Updated {p['name']} Qty")
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
