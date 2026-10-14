import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'ayoub_secret_key_12345'

# بيانات الدخول للأدمن
ADMIN_USERNAME = 'Ayoub'
ADMIN_PASSWORD = '677667'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # جدول الزبائن
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # جدول الطلبات (بدون service_type)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            device TEXT NOT NULL,
            imei TEXT,
            problem TEXT NOT NULL,
            image_filename TEXT NOT NULL,
            status TEXT DEFAULT 'جديد',
            price TEXT DEFAULT '',
            note TEXT DEFAULT '',
            receipt_filename TEXT DEFAULT '',
            receipt_status TEXT DEFAULT 'قيد التحقق'
        )
    ''')
    conn.commit()
    conn.close()

# ----------------- حسابات ودخول الزبائن -----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        phone = request.form['phone'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO users (name, phone, email, password) VALUES (?, ?, ?, ?)', 
                           (name, phone, email, password))
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            
            session['user_id'] = user_id
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="هذا البريد مسجل مسبقاً! قم بتسجيل الدخول.")

    return render_template('register.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        else:
            return render_template('user_login.html', error="البريد الإلكتروني أو كلمة السر غير صحيحة!")

    return render_template('user_login.html')

@app.route('/user_logout')
def user_logout():
    session.pop('user_id', None)
    return redirect(url_for('user_login'))

@app.route('/history')
def history():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
    orders = cursor.fetchall()
    conn.close()

    return render_template('history.html', orders=orders)

# ----------------- تقديم وتتبع الطلبات -----------------

@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        device = request.form['device']
        imei = request.form.get('imei', '')
        problem = request.form['problem']

        image = request.files['image']
        if image and image.filename != '':
            image_filename = image.filename
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        else:
            image_filename = ''

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (user_id, name, phone, device, imei, problem, image_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, phone, device, imei, problem, image_filename))
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return redirect(url_for('track_order', order_id=order_id))

    return render_template('index.html')

@app.route('/track/<int:order_id>')
def track_order(order_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    conn.close()

    if order:
        return render_template('track.html', order=order)
    return "الطلب غير موجود", 404

@app.route('/upload_receipt/<int:order_id>', methods=['POST'])
def upload_receipt(order_id):
    receipt_image = request.files.get('receipt_image')
    if receipt_image and receipt_image.filename != '':
        receipt_filename = f"receipt_{order_id}_{receipt_image.filename}"
        receipt_image.save(os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename))

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE orders SET receipt_filename = ?, receipt_status = 'قيد التحقق' WHERE id = ?
        ''', (receipt_filename, order_id))
        conn.commit()
        conn.close()

    return redirect(url_for('track_order', order_id=order_id))

# ----------------- لوحة تحكم الأدمن -----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة!'

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    filter_status = request.args.get('filter', 'all')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM orders')
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'جديد'")
    new_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'قيد العمل'")
    progress_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'مكتمل'")
    done_count = cursor.fetchone()[0]

    if filter_status == 'جديد':
        cursor.execute("SELECT * FROM orders WHERE status = 'جديد' ORDER BY id DESC")
    elif filter_status == 'قيد العمل':
        cursor.execute("SELECT * FROM orders WHERE status = 'قيد العمل' ORDER BY id DESC")
    elif filter_status == 'مكتمل':
        cursor.execute("SELECT * FROM orders WHERE status = 'مكتمل' ORDER BY id DESC")
    else:
        cursor.execute('SELECT * FROM orders ORDER BY id DESC')

    orders = cursor.fetchall()
    conn.close()

    counts = {'total': total_count, 'new': new_count, 'progress': progress_count, 'done': done_count}
    return render_template('admin.html', orders=orders, counts=counts, current_filter=filter_status)

@app.route('/update_order/<int:order_id>', methods=['POST'])
def update_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    status = request.form['status']
    price = request.form['price']
    note = request.form['note']
    receipt_status = request.form.get('receipt_status', 'قيد التحقق')
    current_filter = request.args.get('filter', 'all')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders SET status = ?, price = ?, note = ?, receipt_status = ? WHERE id = ?
    ''', (status, price, note, receipt_status, order_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin', filter=current_filter))

@app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    current_filter = request.args.get('filter', 'all')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin', filter=current_filter))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)