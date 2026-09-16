import sqlite3
import os
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'users.db'

app = Flask(__name__, static_folder='.', static_url_path='')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT,
            email TEXT,
            phone TEXT,
            company_name TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )

    customer_columns = {
        row['name'] for row in conn.execute("PRAGMA table_info(customers)").fetchall()
    }
    for column, definition in (
        ('company_name', 'TEXT'),
        ('contact_name', 'TEXT'),
        ('contact_email', 'TEXT'),
        ('contact_phone', 'TEXT'),
    ):
        if column not in customer_columns:
            conn.execute(f"ALTER TABLE customers ADD COLUMN {column} {definition}")

    conn.execute(
        '''
        UPDATE customers
        SET company_name = COALESCE(company_name, company),
            contact_name = COALESCE(contact_name, name),
            contact_email = COALESCE(contact_email, email),
            contact_phone = COALESCE(contact_phone, phone)
        WHERE company_name IS NULL
           OR contact_name IS NULL
           OR contact_email IS NULL
           OR contact_phone IS NULL
        '''
    )

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            unit_price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            customer_name TEXT NOT NULL,
            subject TEXT,
            issue_date TEXT,
            due_date TEXT,
            note TEXT,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
        '''
    )

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS quotation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (quotation_id) REFERENCES quotations(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        '''
    )

    quotation_columns = {
        row['name'] for row in conn.execute("PRAGMA table_info(quotations)").fetchall()
    }
    if 'subject' not in quotation_columns:
        conn.execute("ALTER TABLE quotations ADD COLUMN subject TEXT")

    admin_exists = conn.execute(
        "SELECT 1 FROM users WHERE email = ?",
        ('ainsonicav@gmail.com',)
    ).fetchone()

    if not admin_exists:
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('관리자', 'ainsonicav@gmail.com', 'asonic0911*', 'admin')
        )

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({"success": False, "message": "이메일과 비밀번호를 모두 입력해주세요."}), 400

    login_email = 'ainsonicav@gmail.com' if email == 'admin' else email

    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, name, email, password, role FROM users WHERE email = ? AND password = ? AND role = 'admin'",
        (login_email, password)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"success": False, "message": "이메일 또는 비밀번호가 올바르지 않습니다."}), 401

    return jsonify({
        "success": True,
        "message": "로그인에 성공했습니다.",
        "user": {"email": user['email'], "name": user['name'], "role": user['role']}
    })


@app.route('/api/admins', methods=['GET', 'POST'])
def admins():
    conn = get_db_connection()

    if request.method == 'GET':
        rows = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE role = 'admin' ORDER BY id ASC"
        ).fetchall()
        conn.close()
        return jsonify({"success": True, "admins": [dict(row) for row in rows]})

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not name or not email or not password:
        conn.close()
        return jsonify({"success": False, "message": "이름, 이메일, 비밀번호를 모두 입력해주세요."}), 400

    admin_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin'"
    ).fetchone()[0]
    if admin_count >= 5:
        conn.close()
        return jsonify({"success": False, "message": "관리자는 최대 5명까지 설정할 수 있습니다."}), 400

    try:
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'admin')",
            (name, email, password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 등록된 이메일입니다."}), 409

    conn.close()
    return jsonify({"success": True, "message": "관리자가 등록되었습니다."}), 201


@app.route('/api/admins/<int:admin_id>', methods=['PUT'])
def update_admin(admin_id):
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not name or not email:
        return jsonify({"success": False, "message": "이름과 이메일을 입력해주세요."}), 400

    conn = get_db_connection()
    current = conn.execute(
        "SELECT password FROM users WHERE id = ? AND role = 'admin'",
        (admin_id,)
    ).fetchone()
    if not current:
        conn.close()
        return jsonify({"success": False, "message": "관리자를 찾을 수 없습니다."}), 404

    try:
        conn.execute(
            "UPDATE users SET name = ?, email = ?, password = ? WHERE id = ? AND role = 'admin'",
            (name, email, password or current['password'], admin_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "이미 등록된 이메일입니다."}), 409

    conn.close()
    return jsonify({"success": True, "message": "관리자 정보가 수정되었습니다."})


@app.route('/api/customers', methods=['GET', 'POST'])
def customers():
    if request.method == 'GET':
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT id, company_name, contact_name, contact_email, contact_phone, name, company, email, phone, created_at FROM customers ORDER BY id ASC"
        ).fetchall()
        conn.close()
        return jsonify({"success": True, "customers": [dict(row) for row in rows]})

    data = request.get_json(silent=True) or {}
    company_name = (data.get('company_name') or data.get('company') or '').strip()
    contact_name = (data.get('contact_name') or data.get('name') or '').strip()
    contact_email = (data.get('contact_email') or data.get('email') or '').strip()
    contact_phone = (data.get('contact_phone') or data.get('phone') or '').strip()

    if not company_name or not contact_name:
        return jsonify({"success": False, "message": "회사명과 담당자명을 입력해주세요."}), 400

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO customers (name, company, email, phone, company_name, contact_name, contact_email, contact_phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (contact_name, company_name, contact_email, contact_phone, company_name, contact_name, contact_email, contact_phone)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "고객이 등록되었습니다."}), 201


@app.route('/api/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    data = request.get_json(silent=True) or {}
    company_name = (data.get('company_name') or '').strip()
    contact_name = (data.get('contact_name') or '').strip()
    contact_email = (data.get('contact_email') or '').strip()
    contact_phone = (data.get('contact_phone') or '').strip()

    if not company_name or not contact_name:
        return jsonify({"success": False, "message": "회사명과 담당자명을 입력해주세요."}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE customers SET name = ?, company = ?, email = ?, phone = ?, company_name = ?, contact_name = ?, contact_email = ?, contact_phone = ? WHERE id = ?",
        (contact_name, company_name, contact_email, contact_phone, company_name, contact_name, contact_email, contact_phone, customer_id)
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({"success": False, "message": "고객사를 찾을 수 없습니다."}), 404
    return jsonify({"success": True, "message": "고객사가 수정되었습니다."})


@app.route('/api/products', methods=['GET', 'POST'])
def products():
    if request.method == 'GET':
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT id, name, category, unit_price, stock, description, created_at FROM products ORDER BY id ASC"
        ).fetchall()
        conn.close()
        return jsonify({"success": True, "products": [dict(row) for row in rows]})

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    unit_price = data.get('unit_price')
    stock = data.get('stock', 0)
    description = (data.get('description') or '').strip()

    if not name or unit_price is None:
        return jsonify({"success": False, "message": "제품명과 단가를 입력해주세요."}), 400

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (name, category, unit_price, stock, description) VALUES (?, ?, ?, ?, ?)",
        (name, category, float(unit_price), int(stock), description)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "제품이 등록되었습니다."}), 201


@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    category = (data.get('category') or '').strip()
    unit_price = data.get('unit_price')
    description = (data.get('description') or '').strip()

    if not name or not category or unit_price is None:
        return jsonify({"success": False, "message": "품목, 사양, 판매 단가를 입력해주세요."}), 400

    conn = get_db_connection()
    cursor = conn.execute(
        "UPDATE products SET name = ?, category = ?, unit_price = ?, description = ? WHERE id = ?",
        (name, category, float(unit_price), description, product_id)
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({"success": False, "message": "제품을 찾을 수 없습니다."}), 404
    return jsonify({"success": True, "message": "제품이 수정되었습니다."})


@app.route('/api/quotations', methods=['GET', 'POST'])
def quotations():
    if request.method == 'GET':
        conn = get_db_connection()
        rows = conn.execute(
            """
            SELECT quotations.id, quotations.customer_id, quotations.customer_name,
                   quotations.issue_date, quotations.due_date, quotations.total_amount,
                   quotations.status, quotations.created_at,
                   customers.contact_name
            FROM quotations
            LEFT JOIN customers ON customers.id = quotations.customer_id
            ORDER BY quotations.id DESC
            """
        ).fetchall()
        conn.close()
        return jsonify({"success": True, "quotations": [dict(row) for row in rows]})

    data = request.get_json(silent=True) or {}
    customer_id = data.get('customer_id')
    customer_name = (data.get('customer_name') or '').strip()
    subject = (data.get('subject') or '').strip()
    issue_date = data.get('issue_date')
    due_date = data.get('due_date')
    note = (data.get('note') or '').strip()
    items = data.get('items') or []

    if not customer_id and not customer_name:
        return jsonify({"success": False, "message": "고객을 선택해주세요."}), 400

    if not items:
        return jsonify({"success": False, "message": "견적 항목을 최소 1개 이상 추가해주세요."}), 400

    total_amount = 0
    for item in items:
        quantity = int(item.get('quantity', 0))
        unit_price = float(item.get('unit_price', 0))
        total_amount += quantity * unit_price

    conn = get_db_connection()
    customer_row = conn.execute(
        "SELECT company_name, company, name FROM customers WHERE id = ?",
        (customer_id,)
    ).fetchone()

    if customer_row:
        customer_name = customer_row['company_name'] or customer_row['company'] or customer_row['name']

    cursor = conn.execute(
        "INSERT INTO quotations (customer_id, customer_name, subject, issue_date, due_date, note, total_amount, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')",
        (customer_id, customer_name, subject, issue_date, due_date, note, total_amount)
    )
    quotation_id = cursor.lastrowid

    for item in items:
        product_id = item.get('product_id')
        product_name = item.get('product_name')
        quantity = int(item.get('quantity', 0))
        unit_price = float(item.get('unit_price', 0))
        amount = quantity * unit_price
        conn.execute(
            "INSERT INTO quotation_items (quotation_id, product_id, product_name, quantity, unit_price, amount) VALUES (?, ?, ?, ?, ?, ?)",
            (quotation_id, product_id, product_name, quantity, unit_price, amount)
        )

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "견적서가 저장되었습니다.", "quotation_id": quotation_id}), 201


@app.route('/api/quotations/<int:quotation_id>', methods=['GET'])
def quotation_detail(quotation_id):
    conn = get_db_connection()
    quotation = conn.execute(
        """
        SELECT quotations.id, quotations.customer_name, quotations.subject, quotations.issue_date,
               quotations.due_date, quotations.note, quotations.total_amount,
               quotations.status, quotations.created_at,
               customers.contact_name, customers.contact_phone, customers.contact_email
        FROM quotations
        LEFT JOIN customers ON customers.id = quotations.customer_id
        WHERE quotations.id = ?
        """,
        (quotation_id,)
    ).fetchone()

    if not quotation:
        conn.close()
        return jsonify({"success": False, "message": "견적서를 찾을 수 없습니다."}), 404

    items = conn.execute(
        """
        SELECT quotation_items.product_name, quotation_items.quantity,
               quotation_items.unit_price, quotation_items.amount,
               products.category AS product_category
        FROM quotation_items
        LEFT JOIN products ON products.id = quotation_items.product_id
        WHERE quotation_items.quotation_id = ?
        ORDER BY quotation_items.id ASC
        """,
        (quotation_id,)
    ).fetchall()
    conn.close()

    result = dict(quotation)
    result['items'] = [dict(item) for item in items]
    return jsonify({"success": True, "quotation": result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
