import os
import sqlite3
from decimal import Decimal, InvalidOperation
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "banking.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        account_number TEXT NOT NULL UNIQUE,
        balance_cents INTEGER NOT NULL DEFAULT 0 CHECK(balance_cents >= 0),
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
        description TEXT NOT NULL,
        created_at TEXT NOT NULL,
        related_account TEXT,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    );
    CREATE INDEX IF NOT EXISTS idx_transactions_account_date
        ON transactions(account_id, created_at DESC);
    """)
    db.commit()
    db.close()

def money_to_cents(value):
    try:
        amount = Decimal(value).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid amount.")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return int(amount * 100)

def cents_to_money(cents):
    return f"₹{cents / 100:,.2f}"

@app.template_filter("money")
def money_filter(cents):
    return cents_to_money(cents)

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def current_account():
    return get_db().execute(
        "SELECT a.*, u.full_name, u.email FROM accounts a JOIN users u ON u.id=a.user_id WHERE u.id=?",
        (session["user_id"],)
    ).fetchone()

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            flash("Please fill in every field.", "danger")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("register.html")
        db = get_db()
        account_number = "10" + datetime.now().strftime("%y%m%d%H%M%S") + str(os.urandom(2).hex()).upper()
        try:
            cur = db.execute(
                "INSERT INTO users(full_name,email,password_hash,created_at) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="seconds"))
            )
            user_id = cur.lastrowid
            db.execute(
                "INSERT INTO accounts(user_id,account_number,balance_cents,created_at) VALUES(?,?,?,?)",
                (user_id, account_number, 0, datetime.now().isoformat(timespec="seconds"))
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("That email is already registered.", "danger")
            return render_template("register.html")
        session.clear()
        session["user_id"] = user_id
        flash("Account created successfully. Welcome!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    account = current_account()
    txs = get_db().execute(
        "SELECT * FROM transactions WHERE account_id=? ORDER BY id DESC LIMIT 6",
        (account["id"],)
    ).fetchall()
    total_in = get_db().execute(
        "SELECT COALESCE(SUM(amount_cents),0) total FROM transactions WHERE account_id=? AND transaction_type IN ('DEPOSIT','TRANSFER_IN')",
        (account["id"],)
    ).fetchone()["total"]
    total_out = get_db().execute(
        "SELECT COALESCE(SUM(amount_cents),0) total FROM transactions WHERE account_id=? AND transaction_type IN ('WITHDRAWAL','TRANSFER_OUT')",
        (account["id"],)
    ).fetchone()["total"]
    return render_template("dashboard.html", account=account, transactions=txs, total_in=total_in, total_out=total_out)

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        try:
            amount = money_to_cents(request.form.get("amount", ""))
            db = get_db()
            account = current_account()
            db.execute("UPDATE accounts SET balance_cents=balance_cents+? WHERE id=?", (amount, account["id"]))
            db.execute(
                "INSERT INTO transactions(account_id,transaction_type,amount_cents,description,created_at) VALUES(?,?,?,?,?)",
                (account["id"], "DEPOSIT", amount, "Cash deposit (demo)", datetime.now().isoformat(timespec="seconds"))
            )
            db.commit()
            flash(f"Deposit of {cents_to_money(amount)} completed.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("transaction_form.html", title="Deposit money", action="Deposit", hint="Add demo funds to your account.", show_recipient=False)

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    if request.method == "POST":
        try:
            amount = money_to_cents(request.form.get("amount", ""))
            db = get_db()
            account = current_account()
            if account["balance_cents"] < amount:
                flash("Insufficient balance.", "danger")
                return render_template("transaction_form.html", title="Withdraw money", action="Withdraw", hint="Withdraw from your demo account.", show_recipient=False)
            db.execute("UPDATE accounts SET balance_cents=balance_cents-? WHERE id=?", (amount, account["id"]))
            db.execute(
                "INSERT INTO transactions(account_id,transaction_type,amount_cents,description,created_at) VALUES(?,?,?,?,?)",
                (account["id"], "WITHDRAWAL", amount, "Cash withdrawal (demo)", datetime.now().isoformat(timespec="seconds"))
            )
            db.commit()
            flash(f"Withdrawal of {cents_to_money(amount)} completed.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("transaction_form.html", title="Withdraw money", action="Withdraw", hint="Withdraw from your demo account.", show_recipient=False)

@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    if request.method == "POST":
        recipient_number = request.form.get("account_number", "").strip()
        try:
            amount = money_to_cents(request.form.get("amount", ""))
            db = get_db()
            sender = current_account()
            recipient = db.execute("SELECT * FROM accounts WHERE account_number=?", (recipient_number,)).fetchone()
            if not recipient:
                raise ValueError("Recipient account was not found.")
            if recipient["id"] == sender["id"]:
                raise ValueError("You cannot transfer money to your own account.")
            if sender["balance_cents"] < amount:
                raise ValueError("Insufficient balance.")
            now = datetime.now().isoformat(timespec="seconds")
            # All transfer updates and records are committed together.
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE accounts SET balance_cents=balance_cents-? WHERE id=?", (amount, sender["id"]))
                db.execute("UPDATE accounts SET balance_cents=balance_cents+? WHERE id=?", (amount, recipient["id"]))
                db.execute(
                    "INSERT INTO transactions(account_id,transaction_type,amount_cents,description,created_at,related_account) VALUES(?,?,?,?,?,?)",
                    (sender["id"], "TRANSFER_OUT", amount, "Transfer sent", now, recipient_number)
                )
                db.execute(
                    "INSERT INTO transactions(account_id,transaction_type,amount_cents,description,created_at,related_account) VALUES(?,?,?,?,?,?)",
                    (recipient["id"], "TRANSFER_IN", amount, "Transfer received", now, sender["account_number"])
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            flash(f"Transferred {cents_to_money(amount)} successfully.", "success")
            return redirect(url_for("dashboard"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("transaction_form.html", title="Transfer money", action="Transfer", hint="Transfer funds to another registered demo account.", show_recipient=True)

@app.route("/transactions")
@login_required
def transactions():
    account = current_account()
    txs = get_db().execute(
        "SELECT * FROM transactions WHERE account_id=? ORDER BY id DESC",
        (account["id"],)
    ).fetchall()
    return render_template("transactions.html", account=account, transactions=txs)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
