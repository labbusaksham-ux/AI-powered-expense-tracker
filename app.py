from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Session ke liye secret key
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-secret-key"
)


# =========================
# DATABASE CONNECTION
# =========================

def get_db():
    conn = sqlite3.connect("expense.db")
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# LOGIN REQUIRED
# =========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")

        return f(*args, **kwargs)

    return decorated_function


# =========================
# AI CATEGORY PREDICTION
# =========================

def predict_category(title):

    title = title.lower()

    food_words = [
        "food", "restaurant", "dinner", "lunch", "breakfast",
        "pizza", "burger", "chai", "tea", "coffee", "samosa",
        "kachori", "momos", "dosa", "idli", "biryani", "thali",
        "paratha", "roti", "sabzi", "dal", "rice", "noodles",
        "maggi", "sandwich", "cake", "ice cream", "snacks",
        "paneer", "shahi paneer", "palak paneer", "chole",
        "chana", "rajma", "dal makhani", "puri", "bhatura",
        "naan", "tandoori", "kebab", "pakora", "pakode",
        "chaat", "golgappa", "pani puri", "jalebi",
        "gulab jamun", "rasgulla", "ladoo", "halwa",
        "fries", "french fries", "hot dog", "pasta",
        "manchurian", "spring roll", "roll", "wrap",
        "shawarma", "bhelpuri", "pav bhaji"
    ]

    travel_words = [
        "bus", "train", "auto", "uber", "ola",
        "travel", "fuel", "petrol", "diesel"
    ]

    shopping_words = [
        "shopping", "shop", "clothes", "shirt",
        "shoes", "amazon", "flipkart"
    ]

    bills_words = [
        "bill", "electricity", "recharge",
        "internet", "mobile", "rent"
    ]

    health_words = [
        "medicine", "doctor", "hospital", "health"
    ]

    education_words = [
        "book", "course", "college",
        "education", "fees"
    ]

    if any(word in title for word in food_words):
        return "Food"

    elif any(word in title for word in travel_words):
        return "Travel"

    elif any(word in title for word in shopping_words):
        return "Shopping"

    elif any(word in title for word in bills_words):
        return "Bills"

    elif any(word in title for word in health_words):
        return "Health"

    elif any(word in title for word in education_words):
        return "Education"

    else:
        return "Other"


# =========================
# CREATE / UPDATE TABLES
# =========================

def create_table():

    conn = get_db()

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # EXPENSES TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            expense_date TEXT NOT NULL
        )
    """)

    # Check expense_date column
    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(expenses)").fetchall()
    ]

    if "expense_date" not in columns:
        conn.execute("""
            ALTER TABLE expenses
            ADD COLUMN expense_date TEXT
        """)

        conn.execute("""
            UPDATE expenses
            SET expense_date = ?
            WHERE expense_date IS NULL
        """, (str(date.today()),))

    # PAYMENTS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            due_day INTEGER NOT NULL
        )
    """)

    # SALARIES TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            salary_date TEXT NOT NULL
        )
    """)

    # BUDGET TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            budget_month TEXT NOT NULL
        )
    """)

    # Add user_id to existing tables
    tables = [
        "expenses",
        "payments",
        "salaries",
        "budgets"
    ]

    for table in tables:

        columns = [
            row["name"]
            for row in conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        ]

        if "user_id" not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN user_id INTEGER"
            )

    conn.commit()
    conn.close()


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        if not username or not email or not password:
            return "Please fill all fields"

        if len(password) < 6:
            return "Password must be at least 6 characters"

        conn = get_db()

        # Check existing email
        existing_user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            conn.close()
            return "Email already registered"

        # Check whether this is first user
        user_count = conn.execute(
            "SELECT COUNT(*) AS count FROM users"
        ).fetchone()["count"]

        hashed_password = generate_password_hash(password)

        cursor = conn.execute("""
            INSERT INTO users
            (username, email, password)
            VALUES (?, ?, ?)
        """, (
            username,
            email,
            hashed_password
        ))

        new_user_id = cursor.lastrowid

        # First user ko old data assign kar do
        if user_count == 0:

            conn.execute("""
                UPDATE expenses
                SET user_id = ?
                WHERE user_id IS NULL
            """, (new_user_id,))

            conn.execute("""
                UPDATE payments
                SET user_id = ?
                WHERE user_id IS NULL
            """, (new_user_id,))

            conn.execute("""
                UPDATE salaries
                SET user_id = ?
                WHERE user_id IS NULL
            """, (new_user_id,))

            conn.execute("""
                UPDATE budgets
                SET user_id = ?
                WHERE user_id IS NULL
            """, (new_user_id,))

        conn.commit()
        conn.close()

        # Login after registration
        session["user_id"] = new_user_id
        session["username"] = username

        return redirect("/")

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect("/")

        return "Invalid email or password"

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# HOME
# =========================

@app.route("/")
@login_required
def index():

    conn = get_db()

    user_id = session["user_id"]
    username = session.get("username")

    if not username:
        user_record = conn.execute("""
            SELECT username
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()
        username = user_record["username"] if user_record else "User"
        session["username"] = username

    # User expenses
    expenses = conn.execute("""
        SELECT *
        FROM expenses
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    # User payments
    payments = conn.execute("""
        SELECT *
        FROM payments
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    # User salaries
    salaries = conn.execute("""
        SELECT *
        FROM salaries
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,)).fetchall()

    # Total expense
    total_expense = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    # Total salary
    total_salary = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM salaries
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    # Remaining balance
    remaining_balance = total_salary - total_expense

    # Current month
    current_month = date.today().strftime("%Y-%m")

    # Current month expense
    monthly_expense = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND substr(expense_date, 1, 7) = ?
    """, (
        user_id,
        current_month
    )).fetchone()[0]

    # Current month budget
    budget = conn.execute("""
        SELECT *
        FROM budgets
        WHERE user_id = ?
        AND budget_month = ?
    """, (
        user_id,
        current_month
    )).fetchone()

    monthly_budget = budget["amount"] if budget else 0

    budget_remaining = monthly_budget - monthly_expense
    today = date.today().day

    if monthly_budget == 0:
        budget_status = "No budget set"

    elif monthly_expense > monthly_budget:
        budget_status = "Budget Exceeded"

    else:
        budget_status = "Within Budget"

    conn.close()

    return render_template(
        "index.html",
        expenses=expenses,
        payments=payments,
        salaries=salaries,
        total_expense=total_expense,
        total_salary=total_salary,
        remaining_balance=remaining_balance,
        current_month=current_month,
        monthly_expense=monthly_expense,
        monthly_budget=monthly_budget,
        budget_remaining=budget_remaining,
        budget_status=budget_status,
        today=today,
        username=username
    )


# =========================
# ADD EXPENSE
# =========================

@app.route("/add", methods=["POST"])
@login_required
def add_expense():

    title = request.form["title"]
    amount = request.form["amount"]
    expense_date = request.form["expense_date"]

    category = predict_category(title)

    conn = get_db()

    conn.execute("""
        INSERT INTO expenses
        (title, amount, category, expense_date, user_id)
        VALUES (?, ?, ?, ?, ?)
    """, (
        title,
        amount,
        category,
        expense_date,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# DELETE EXPENSE
# =========================

@app.route("/delete/<int:id>")
@login_required
def delete_expense(id):

    conn = get_db()

    conn.execute("""
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# ADD PAYMENT
# =========================

@app.route("/add_payment", methods=["POST"])
@login_required
def add_payment():

    title = request.form["payment_title"]
    amount = request.form["payment_amount"]
    due_day = request.form["due_day"]

    conn = get_db()

    conn.execute("""
        INSERT INTO payments
        (title, amount, due_day, user_id)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        amount,
        due_day,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# DELETE PAYMENT
# =========================

@app.route("/delete_payment/<int:id>")
@login_required
def delete_payment(id):

    conn = get_db()

    conn.execute("""
        DELETE FROM payments
        WHERE id = ?
        AND user_id = ?
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# ADD SALARY
# =========================

@app.route("/add_salary", methods=["POST"])
@login_required
def add_salary():

    title = request.form["salary_title"]
    amount = request.form["salary_amount"]
    salary_date = request.form["salary_date"]

    conn = get_db()

    conn.execute("""
        INSERT INTO salaries
        (title, amount, salary_date, user_id)
        VALUES (?, ?, ?, ?)
    """, (
        title,
        amount,
        salary_date,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# DELETE SALARY
# =========================

@app.route("/delete_salary/<int:id>")
@login_required
def delete_salary(id):

    conn = get_db()

    conn.execute("""
        DELETE FROM salaries
        WHERE id = ?
        AND user_id = ?
    """, (
        id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/")


# =========================
# SET MONTHLY BUDGET
# =========================

@app.route("/set_budget", methods=["POST"])
@login_required
def set_budget():

    amount = request.form["budget_amount"]

    current_month = date.today().strftime("%Y-%m")

    user_id = session["user_id"]

    conn = get_db()

    existing_budget = conn.execute("""
        SELECT id
        FROM budgets
        WHERE user_id = ?
        AND budget_month = ?
    """, (
        user_id,
        current_month
    )).fetchone()

    if existing_budget:

        conn.execute("""
            UPDATE budgets
            SET amount = ?
            WHERE user_id = ?
            AND budget_month = ?
        """, (
            amount,
            user_id,
            current_month
        ))

    else:

        conn.execute("""
            INSERT INTO budgets
            (amount, budget_month, user_id)
            VALUES (?, ?, ?)
        """, (
            amount,
            current_month,
            user_id
        ))

    conn.commit()
    conn.close()

    return redirect("/")


# Initialize the database for both local runs and Gunicorn imports.
create_table()

if __name__ == "__main__":
    app.run(debug=False)