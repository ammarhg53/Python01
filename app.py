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
    .card h4 { color: #000000 !important; font-weight: bold; margin: 0; }
    .card p { color: #333333 !important; }
    .stock-green { color: green !important; font-weight: bold; }
    .stock-red { color: red !important; font-weight: bold; }
    .big-font { font-size: 18px !important; }
    .main-header { font-size: 24px; font-weight: bold; color: #333; }
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
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user, error_msg = User.login(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error(error_msg)

# ==========================================
# ADMIN PANEL
# ==========================================
def admin_panel():
    st.sidebar.header(f"👤 Admin: {st.session_state.user.username}")
    nav = st.sidebar.radio("Menu", ["Analytics", "Orders & Cancellations", "Inventory", "Settings", "Profile", "Manage Operators"])
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()
        
    db = DatabaseManager()
    conn = db.get_connection()

    if nav == "Analytics":
        st.title("📈 Advanced Business Analytics")
        
        c1, c2 = st.columns(2)
        start_d = c1.date_input("From", value=pd.to_datetime("2025-01-01"))
        end_d = c2.date_input("To", value=pd.to_datetime("today"))
        
        engine = AnalyticsEngine()
        data = engine.get_financials_extended(start_d, end_d)
        
        # Financial Metrics (Excluding Cancelled)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Revenue", f"₹{data['revenue']:,.0f}")
        m2.metric("Orders", data['total_orders'])
        m3.metric("Avg Order Value", f"₹{data['aov']:,.0f}")
        m4.metric("Total Cost", f"₹{data['total_cost']:,.0f}")
        m5.metric("Gross Profit", f"₹{data['gross_profit']:,.0f}")
        
        st.divider()

        # Tabs for detailed analytics
        at1, at2, at3, at4 = st.tabs(["Sales Trends", "Product Performance", "Category & Payment", "Predictions"])
        
        with at1:
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("⏰ Peak Sales Hours")
                hourly = engine.get_hourly_trends()
                if not hourly.empty:
                    st.bar_chart(hourly.set_index('hour')['orders'])
                else:
                    st.info("No data")
            with col_b:
                st.subheader("📅 Busiest Days")
                daily = engine.get_daily_trends()
                if not daily.empty:
                    st.bar_chart(daily.set_index('day_name')['orders'])
                else:
                    st.info("No data")

        with at2:
            st.subheader("🏆 Top Selling Products (Qty)")
            top_prod = engine.get_top_selling_products()
            st.table(top_prod)

        with at3:
            col_c, col_d = st.columns(2)
            with col_c:
                st.subheader("📂 Category Sales")
                cat_stats = engine.get_category_analytics()
                st.bar_chart(cat_stats.set_index('name')['total_sold'])
            with col_d:
                st.subheader("💳 Payment Patterns")
                pay_stats = engine.get_payment_patterns()
                if not pay_stats.empty:
                    fig, ax = plt.subplots()
                    ax.pie(pay_stats['count'], labels=pay_stats['payment_mode'], autopct='%1.1f%%', startangle=90)
                    st.pyplot(fig)

        with at4:
            st.subheader("🔮 Sales Forecasting")
            reg_mode = st.radio("Regression Model", ["Linear", "Optimized (Smoothed)"], horizontal=True)
            sales_df = engine.get_sales_report(start_d, end_d)
            if not sales_df.empty:
                (X, y_fit), (fut_X, fut_y) = engine.predict_sales(sales_df, mode="Linear" if "Linear" in reg_mode else "Optimized")
                if X is not None:
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.scatter(sales_df['date'], sales_df['sales'], color='blue', label='Actual')
                    ax.plot(sales_df['date'], y_fit, color='green', linestyle='--', label='Trend')
                    ax.set_title(f"Sales Trend ({reg_mode})")
                    plt.xticks(rotation=45)
                    ax.legend()
                    st.pyplot(fig)

    elif nav == "Orders & Cancellations":
        st.title("📦 Order Management & Audit")
        
        # Filter
        st.subheader("Order History")
        filter_status = st.selectbox("Filter Status", ["All", "active", "cancelled"])
        
        # Enhanced query to include customer name
        query = """
            SELECT o.order_id, o.timestamp, c.name as customer_name, o.customer_mobile, o.total_amount, o.status, o.cancellation_reason 
            FROM orders o 
            LEFT JOIN customers c ON o.customer_mobile = c.mobile
        """
        conditions = []
        if filter_status != "All":
            conditions.append(f"o.status='{filter_status}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY o.timestamp DESC"
        
        orders_df = pd.read_sql_query(query, conn)
        st.dataframe(orders_df, use_container_width=True)
        
        st.divider()
        st.subheader("❌ Cancel Order")
        
        # Session state for form persistence/clearing
        if 'c_oid' not in st.session_state: st.session_state.c_oid = ""
        if 'c_reason' not in st.session_state: st.session_state.c_reason = ""
        if 'c_pass' not in st.session_state: st.session_state.c_pass = ""

        # Using a callback-like structure for form submission to handle clearing correctly
        with st.form("cancel_form"):
            oid_input = st.text_input("Order ID to Cancel", value=st.session_state.c_oid)
            reason_input = st.text_input("Reason for Cancellation", value=st.session_state.c_reason)
            pass_input = st.text_input("Admin Password Confirmation", type="password", value=st.session_state.c_pass)
            
            submitted = st.form_submit_button("Cancel Order")
            
            if submitted:
                if not oid_input or not reason_input or not pass_input:
                    st.error("All fields are mandatory")
                    # Preserve inputs
                    st.session_state.c_oid = oid_input
                    st.session_state.c_reason = reason_input
                    st.session_state.c_pass = pass_input
                    st.rerun()
                else:
                    success, msg = st.session_state.user.cancel_order(oid_input, reason_input, pass_input)
                    if success:
                        st.success(msg)
                        # Clear inputs only on success
                        st.session_state.c_oid = ""
                        st.session_state.c_reason = ""
                        st.session_state.c_pass = ""
                        st.rerun()
                    else:
                        st.error(msg)
                        # Preserve inputs on failure
                        st.session_state.c_oid = oid_input
                        st.session_state.c_reason = reason_input
                        st.session_state.c_pass = pass_input
                        st.rerun()

    elif nav == "Inventory":
        st.title("📦 Inventory Manager")
        tab1, tab2, tab3, tab4 = st.tabs(["View Products", "Add Product", "Restock", "Manage Categories"])
        
        with tab1:
            search_q = st.text_input("Search Product")
            df = pd.read_sql_query("SELECT p.id, p.name, c.name as category, p.stock, p.selling_price FROM products p JOIN categories c ON p.category_id=c.id", conn)
            if search_q:
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
                elif re.match(r'^(item|product)', name, re.IGNORECASE):
                    st.error("Generic names like 'Item' are not allowed.")
                elif cost <= 0 or sell <= 0:
                    st.error("Price must be greater than 0")
                elif stock < 0:
                    st.error("Stock cannot be negative")
                else:
                    conn.execute("INSERT INTO products (name, category_id, selling_price, cost_price, stock, sales_count) VALUES (?, ?, ?, ?, ?, ?)",
                                 (name.strip(), cat_id, sell, cost, stock, 0))
                    conn.commit()
                    st.success("Added")

        with tab3:
            st.markdown("#### Restock Inventory")
            prods = pd.read_sql_query("SELECT id, name, stock FROM products", conn)
            pid = st.selectbox("Select Product", prods['id'], format_func=lambda x: f"{prods[prods['id']==x]['name'].values[0]} (Curr: {prods[prods['id']==x]['stock'].values[0]})")
            qty = st.number_input("Quantity to Add", min_value=1, value=1)
            if st.button("Update Stock"):
                if st.session_state.user.restock_product(pid, qty):
                    st.success("Stock Updated")
                    st.rerun()
                else:
                    st.error("Failed")

        with tab4:
            st.markdown("#### Category Management")
            cats = pd.read_sql_query("SELECT * FROM categories", conn)
            c1, c2 = st.columns(2)
            with c1:
                new_cat = st.text_input("New Category Name")
                if st.button("Add Category"):
                    if st.session_state.user.manage_category('add', new_cat):
                        st.success("Added")
                        st.rerun()
                    else:
                        st.error("Error")
            with c2:
                target_cat = st.selectbox("Select Category to Rename", cats['name'])
                rename_val = st.text_input("Rename to")
                if st.button("Rename"):
                    if st.session_state.user.manage_category('rename', target_cat, rename_val):
                        st.success("Renamed")
                        st.rerun()
                    else:
                        st.error("Error")

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
            st.success("Saved")

    elif nav == "Profile":
        profile_section()

    elif nav == "Manage Operators":
        st.title("👥 Create POS Operator")
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        strength = User.check_strength(new_pass)
        st.progress(strength/5)
        if st.button("Create Operator"):
            if strength < 5:
                st.error("Password Weak")
            elif st.session_state.user.create_operator("Operator", new_user, new_pass):
                st.success("Created")
            else:
                st.error("Exists")

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
            mobile_input = c2.text_input("Mobile Number", max_chars=10)
            valid_mobile = False
            cust_name = ""
            
            if mobile_input:
                # India validation
                if country == "India (+91)":
                    if re.match(r"^[6-9]\d{9}$", mobile_input):
                        valid_mobile = True
                    else:
                        st.error("Invalid Mobile Number (10 digits, starts with 6-9)")
                else:
                    # Simple length check for other countries for now based on previous simple rules
                    patterns = {"USA (+1)": r"^\d{10}$", "UAE (+971)": r"^5\d{8}$", "UK (+44)": r"^7\d{9}$"}
                    if re.match(patterns[country], mobile_input):
                        valid_mobile = True
                    else:
                        st.error("Invalid Mobile Number format")

                if valid_mobile:
                    cust = conn.execute("SELECT name FROM customers WHERE mobile=?", (mobile_input,)).fetchone()
                    if cust:
                        cust_name = cust[0]
                        st.success(f"Customer Found: {cust_name}")
                    else:
                        cust_name = st.text_input("New Customer Name (Mandatory)")
                        if not cust_name:
                            valid_mobile = False # Block if name is empty for new customer
                        else:
                            # Register on the fly button logic slightly adjusted
                            if st.button("Register Customer"):
                                conn.execute("INSERT INTO customers (mobile, name) VALUES (?,?)", (mobile_input, cust_name))
                                conn.commit()
                                st.success("Registered")
                                st.rerun()
            
            # Block billing if new customer not registered yet
            # Actually, the logic usually is: enter mobile, if not found, ask name. 
            # If name entered, proceed. We can register implicitly or explicitly. 
            # The prompt says "If mobile does NOT exist: Show input field: Customer Name. Name is mandatory".
            # We will handle the implicit registration during order processing or explicit via button.
            # For smoother flow, we'll keep the implicit registration logic if we can, or just force them to check.
            # To stick to "Register Customer" flow from previous code:
            if valid_mobile and not cust_name and not cust: 
                 st.info("Please enter name and register to proceed.")

        col_prod, col_cart = st.columns([2, 1])
        
        # 2. Product Grid (Clean Text-Based Cards)
        with col_prod:
            st.subheader("Products")
            algo_choice = st.radio("Search Algorithm", ["Linear Search (O(n))", "Binary Search (O(log n))"], horizontal=True)
            if "Linear" in algo_choice: st.session_state.search_mode = "Linear"
            else: st.session_state.search_mode = "Binary"

            search = st.text_input("Search Item")
            all_products = pd.read_sql_query("SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id=c.id", conn).to_dict('records')
            
            if search:
                if st.session_state.search_mode == "Linear": filtered_products = SearchAlgorithms.linear_search(all_products, "name", search)
                else: filtered_products = SearchAlgorithms.binary_search(all_products, "name", search)
            else:
                filtered_products = all_products

            total_items = len(filtered_products)
            total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if st.button("⬅️ Prev") and st.session_state.prod_page > 0: st.session_state.prod_page -= 1
            with pc2:
                st.markdown(f"<div style='text-align: center'>Page {st.session_state.prod_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
            with pc3:
                if st.button("Next ➡️") and st.session_state.prod_page < total_pages - 1: st.session_state.prod_page += 1

            start_idx = st.session_state.prod_page * ITEMS_PER_PAGE
            page_items = filtered_products[start_idx:start_idx + ITEMS_PER_PAGE]
            
            cols = st.columns(3)
            for idx, p in enumerate(page_items):
                with cols[idx % 3]:
                    # Clean Card UI (No Images, forced Black Text)
                    st.markdown(f"""
                    <div class="card">
                        <h4>{p['name']}</h4>
                        <p>{p['category_name']}</p>
                        <h3>₹{p['selling_price']}</h3>
                        <p class="{'stock-green' if p['stock']>0 else 'stock-red'}">
                            {'IN STOCK: ' + str(p['stock']) if p['stock']>0 else 'OUT OF STOCK'}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if p['stock'] > 0:
                        if st.button("Add 🛒", key=f"add_{p['id']}"):
                            if p['id'] in st.session_state.cart:
                                if st.session_state.cart[p['id']]['qty'] < p['stock']:
                                    st.session_state.cart[p['id']]['qty'] += 1
                                    st.toast(f"Updated {p['name']}")
                                else:
                                    st.toast("Max stock reached")
                            else:
                                st.session_state.cart[p['id']] = p
                                st.session_state.cart[p['id']]['qty'] = 1
                                st.toast(f"Added {p['name']}")
                    else:
                        st.button("🚫", disabled=True, key=f"no_{p['id']}")

        # 3. Cart
        with col_cart:
            st.subheader("Cart")
            if not st.session_state.cart:
                st.info("Empty")
            else:
                total_val = 0
                for pid, item in list(st.session_state.cart.items()):
                    with st.container():
                        st.write(f"**{item['name']}**")
                        cc1, cc2, cc3 = st.columns([2, 1, 1])
                        
                        # Qty Control
                        with cc1:
                            new_qty = st.number_input(
                                f"Qty", 
                                min_value=1, 
                                max_value=int(item['stock']), 
                                value=int(item['qty']), 
                                key=f"qty_{pid}",
                                label_visibility="collapsed"
                            )
                            if new_qty != item['qty']:
                                st.session_state.cart[pid]['qty'] = new_qty
                                st.rerun()

                        with cc2:
                            st.write(f"₹{item['selling_price'] * item['qty']:.0f}")
                        
                        with cc3:
                            if st.button("🗑️", key=f"del_{pid}"):
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
                
                pay_mode = st.radio("Payment Mode", ["Cash", "Card", "UPI"])
                card_valid = True
                
                if pay_mode == "Card":
                    c_name = st.text_input("Card Holder Name")
                    c_num = st.text_input("Card No (16 digits)", max_chars=16)
                    c1, c2 = st.columns(2)
                    c_exp = c1.text_input("Expiry (MM/YY)", max_chars=5)
                    c_cvv = c2.text_input("CVV", max_chars=3, type="password")
                    
                    if c_name and c_num and c_exp and c_cvv:
                        # Validation
                        if not re.match(r"^[a-zA-Z\s]+$", c_name): 
                            st.error("Invalid Name")
                            card_valid = False
                        if not re.match(r"^\d{16}$", c_num): 
                            st.error("Invalid Card Number")
                            card_valid = False
                        if not re.match(r"^\d{3}$", c_cvv): 
                            st.error("Invalid CVV")
                            card_valid = False
                        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", c_exp): 
                            st.error("Invalid Expiry (MM/YY)")
                            card_valid = False
                    else:
                        card_valid = False # Fields empty

                elif pay_mode == "UPI":
                    if final_total > 0:
                        qr_path = generate_qr(settings.get("upi_id"), settings.get("store_name"), final_total)
                        st.image(qr_path, caption="Scan", width=200)

                # Complete Order Button
                # Needs valid mobile (and if new, registered), valid cart, and valid payment
                proceed_enabled = valid_mobile and final_total > 0 and cust_name
                if pay_mode == "Card" and not card_valid:
                    proceed_enabled = False

                if st.button("✅ Complete Order", disabled=not proceed_enabled):
                    # Double check if customer exists, if not create on the fly (for implicit case)
                    check_cust = conn.execute("SELECT mobile FROM customers WHERE mobile=?", (mobile_input,)).fetchone()
                    if not check_cust:
                         conn.execute("INSERT INTO customers (mobile, name) VALUES (?,?)", (mobile_input, cust_name))
                         conn.commit()
                    
                    gst_config = {'enabled': settings.get("gst_enabled")=="True", 'percent': float(settings.get("gst_percent", 18))}
                    oid, tot, gst = st.session_state.user.process_order(mobile_input, st.session_state.cart, pay_mode, gst_config)
                    
                    # Generate PDF with Correct Filename logic
                    inv_data = {
                        'id': oid, 'store_name': settings.get("store_name"),
                        'customer_name': cust_name, 'customer_mobile': mobile_input,
                        'items': st.session_state.cart.values(), 'gst': gst, 'total': tot
                    }
                    pdf_file = generate_pdf(inv_data)
                    
                    # Read generated PDF for download button
                    with open(pdf_file, "rb") as f:
                        pdf_data = f.read()

                    # Success and Download (No Rerun immediately to allow download)
                    st.success(f"Order {oid} Successful!")
                    st.download_button("📄 Download Bill", data=pdf_data, file_name=pdf_file, mime="application/pdf")
                    
                    # Clear Cart
                    st.session_state.cart = {}
                    # Removed st.rerun() so download button is visible

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
                    st.success("Updated")
                else:
                    st.error("Weak Password")
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
