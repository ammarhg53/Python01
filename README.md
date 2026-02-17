# 📦 Smart Inventory Enterprise System

A full-featured **Inventory Management & POS Billing System** built using **Python, Streamlit, SQLite, and NumPy**.

This project helps manage products, billing, customers, analytics, and reports in a simple web interface. It is designed for small retail stores and educational demonstration.

---

## 🚀 Features

### 👤 User Roles
- Admin login with full control
- POS Operator login for billing

### 📦 Inventory Management
- Add new products
- Manage categories
- Restock items
- Track stock levels
- Track product sales

### 🛒 POS Billing System
- Customer registration using mobile number
- Add items to cart
- Automatic GST calculation
- Multiple payment modes:
  - Cash
  - Card
  - UPI QR
- Invoice generation in PDF format
- QR code payment support

### 📊 Analytics Dashboard
- Revenue and order statistics
- Average order value
- Category performance
- Payment pattern analysis
- Peak sales hours
- Daily sales trends
- Future sales prediction graph

### 🔐 Security & Validation
- Password hashing using SHA-256
- Mobile number validation
- Card validation using Luhn Algorithm
- Expiry date validation

---

## 🛠️ Technologies Used

- **Python**
- **Streamlit**
- **SQLite**
- **NumPy**
- **Matplotlib**
- **FPDF** (for PDF invoices)
- **QRCode** (for UPI payments)

---

## 📂 Project Structure

```
SmartInventory/
│
├── app.py                     # Streamlit UI
├── backend.py                 # Database & logic layer
├── smart_inventory_pro.db     # SQLite database
├── requirements.txt           # Dependencies
└── README.md
```

---

## ▶️ How to Run the Project

### 1️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 2️⃣ Run the Application

```bash
streamlit run app.py
```

### 3️⃣ Open in Browser

Streamlit will automatically open:

```
http://localhost:8501
```

---

## 🔑 Demo Login Credentials

### Admin Login
```
Username: admin
Password: Admin@123
```

### POS Operator Login
```
Username: pos1
Password: Pos@123
```

---

## 📊 Sales Prediction Logic

The system predicts future sales based on past trends.  
It creates a mathematical trend line from historical sales data and extends it to estimate future values for visualization.

---

## 🌐 Live Demo

👉 Scan the QR code or visit the deployed website:  
**[https://python01-abpe3hpuxnbhdzgwtoyzvj.streamlit.app]**

---



## 👨‍💻 Author

**Ammar Husain Gheewala**  
Inventory Management System Project

---

## 📜 License

This project is developed for educational and demonstration purposes.
