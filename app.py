import os
import sqlite3
from datetime import date
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)

# Sessions are signed with this key. Dev fallback only — export SECRET_KEY
# before this is ever deployed.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Reduces CSRF exposure. Flask 3.1 defaults this to None, which modern browsers
# already treat as Lax, so this pins the existing behaviour rather than changing it.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Create the database and demo data before any route can use them.
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def normalize_email(raw):
    """How an email is stored and looked up — registration and login must agree."""
    return (raw or "").strip().lower()


def _is_valid_email(email):
    """Minimal sanity check: one @, a non-empty local part, and a dotted domain."""
    if email.count("@") != 1:
        return False
    local, _, domain = email.partition("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def inr(amount):
    """Format a rupee amount with Indian digit grouping: ₹9,747 / ₹1,23,456.

    Templates must not do arithmetic and Jinja has no thousands separator, so
    every amount is formatted here before it reaches the page. Indian grouping
    is last-three-then-pairs, not the western three-then-pairs.
    """
    digits = str(round(amount))
    if len(digits) <= 3:
        return f"₹{digits}"

    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"₹{','.join(groups)},{tail}"


def _initials(name):
    """First letters of the first two words, for the avatar circle."""
    return "".join(part[0] for part in name.split()[:2]).upper()


def guest_only(view):
    """Redirect already-signed-in visitors away from the sign-in and sign-up pages.

    Applied below @app.route so Flask registers the wrapped function; functools.wraps
    preserves __name__, which keeps the endpoint name and url_for() working.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return view(*args, **kwargs)
    return wrapped


def login_required(view):
    """Redirect signed-out visitors to the sign-in page.

    Applied below @app.route so Flask registers the wrapped function; functools.wraps
    preserves __name__, which keeps the endpoint name and url_for() working.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
@guest_only
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")  # never stripped — it is the credential

    error = None
    if not name or not email or not password.strip():
        error = "All fields are required."
    elif not _is_valid_email(email):
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."

    if error is None:
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing is not None:
                # NOTE: this message deliberately reveals that an address is
                # registered. That is the right UX for a signup form, but it means
                # registration — unlike login — is an enumeration oracle.
                error = "An account with that email already exists."
            else:
                try:
                    cursor = conn.execute(
                        "INSERT INTO users (name, email, password_hash)"
                        " VALUES (?, ?, ?)",
                        (name, email, generate_password_hash(password)),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    # Race: another request inserted the same email between the
                    # check above and this insert.
                    conn.rollback()
                    error = "An account with that email already exists."
                else:
                    session.clear()
                    session["user_id"] = cursor.lastrowid
                    # Cached so the navbar can greet the user without a query
                    # on every page render — see the profile step.
                    session["user_name"] = name
                    return redirect(url_for("landing"))
        finally:
            conn.close()

    return render_template("register.html", error=error, name=name, email=email)


@app.route("/login", methods=["GET", "POST"])
@guest_only
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = normalize_email(request.form.get("email"))
    password = request.form.get("password", "")

    error = None
    if not email or not password:
        error = "Email and password are required."

    if error is None:
        conn = get_db()
        try:
            user = conn.execute(
                "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
        finally:
            conn.close()

        # One message for both failure modes: a distinct "no such account" reply
        # would let anyone enumerate registered addresses. Accepted trade-off:
        # `or` short-circuits, so an unknown email skips the scrypt check and
        # responds measurably faster. Fixing that needs a dummy-hash comparison.
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("landing"))

    return render_template("login.html", error=error, email=email)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

# ------------------------------------------------------------------ #
# Profile data — hardcoded, replaced by real queries in Step 5        #
# ------------------------------------------------------------------ #

# Mirrors database/db.py's seed: the demo user's own eight expenses, newest
# first, and their real `created_at` date. Keeping this identical to what
# seed_db() writes means Step 5 can swap in a real query without the page
# changing appearance at all — which is the point of building the UI first.
PROFILE_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "member_since": "18 September 2026",
}

# Dicts rather than tuples so the derivation below reads as row["amount"] —
# the same access sqlite3.Row gives once these rows come from a query.
PROFILE_EXPENSES = (
    {"date": "2026-09-16", "description": "Gift for a friend", "category": "Other", "amount": 500.00},
    {"date": "2026-09-14", "description": "Running shoes", "category": "Shopping", "amount": 3199.00},
    {"date": "2026-09-12", "description": "Movie tickets", "category": "Entertainment", "amount": 649.00},
    {"date": "2026-09-10", "description": "Pharmacy", "category": "Health", "amount": 899.00},
    {"date": "2026-09-08", "description": "Electricity bill", "category": "Bills", "amount": 2450.00},
    {"date": "2026-09-06", "description": "Metro card recharge", "category": "Transport", "amount": 320.00},
    {"date": "2026-09-04", "description": "Groceries", "category": "Food", "amount": 1280.00},
    {"date": "2026-09-02", "description": "Lunch with team", "category": "Food", "amount": 450.00},
)


@app.route("/profile")
@login_required
def profile():
    """Render the profile page from hardcoded data — no queries until Step 5.

    Total, transaction count, top category and every bar width are derived from
    PROFILE_EXPENSES rather than written out separately, so no figure on the
    page can drift from the rows it claims to summarise.
    """
    expenses = [
        {
            "date": date.fromisoformat(row["date"]).strftime("%d %b %Y"),
            "description": row["description"],
            "category": row["category"],
            "amount": inr(row["amount"]),
        }
        for row in PROFILE_EXPENSES
    ]

    total = sum(row["amount"] for row in PROFILE_EXPENSES)

    totals = {}
    for row in PROFILE_EXPENSES:
        totals[row["category"]] = totals.get(row["category"], 0) + row["amount"]

    breakdown = [
        {
            "category": category,
            "amount": inr(amount),
            "pct": round(amount / total * 100),
        }
        for category, amount in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return render_template(
        "profile.html",
        user={**PROFILE_USER, "initials": _initials(PROFILE_USER["name"])},
        stats={
            "total_spent": inr(total),
            "expense_count": len(PROFILE_EXPENSES),
            "top_category": breakdown[0]["category"],
        },
        expenses=expenses,
        breakdown=breakdown,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
