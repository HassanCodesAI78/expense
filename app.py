import os
import sqlite3
from datetime import date, datetime
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
# Profile page data                                                   #
# ------------------------------------------------------------------ #
# Each helper below is a pure function over the same `rows` sequence that
# profile() fetches once, so every figure on the page derives from a single
# result set and none can drift from the rows it claims to summarise.

def _profile_expenses(rows):
    """Transaction table rows: display-formatted, in the order given."""
    return [
        {
            "date": date.fromisoformat(row["date"]).strftime("%d %b %Y"),
            "description": row["description"],
            "category": row["category"],
            "amount": inr(row["amount"]),
        }
        for row in rows
    ]


def _profile_stats(rows, breakdown):
    """Summary row. Top category is sourced from the sorted breakdown.

    `breakdown` must be sorted DESCENDING by amount — this reads breakdown[0]
    as "the top category", so the stat card names the same category as the
    tallest bar. An ascending breakdown would silently report the *smallest*
    category with nothing failing. Taking it as an argument rather than
    recomputing keeps the total derived in exactly one place.

    The em-dash placeholder matters: an empty `.profile-stat-value` collapses
    that line, so with no expenses the card loses its baseline against its two
    neighbours.
    """
    total = sum(row["amount"] for row in rows)
    return {
        "total_spent": inr(total),
        "expense_count": len(rows),
        "top_category": breakdown[0]["category"] if breakdown else "—",
    }


def _profile_breakdown(rows):
    """Per-category totals, descending by amount, each with a bar width pct."""
    total = sum(row["amount"] for row in rows)
    # `<= 0`, not `== 0`: a zero total divides by zero, and `amount` carries no
    # CHECK constraint, so a negative total is reachable too — it would emit
    # negative percentages (`width: -33%`), which browsers ignore, collapsing
    # every bar. Both cases return [] and fall through to the empty state.
    if total <= 0:
        return []
    totals = {}
    for row in rows:
        totals[row["category"]] = totals.get(row["category"], 0) + row["amount"]
    return [
        {
            "category": category,
            "amount": inr(amount),
            # Bare int on purpose — the template writes this into `width: N%`.
            # Passing it through inr() would yield `width: ₹33%`, invalid CSS.
            "pct": round(amount / total * 100),
        }
        for category, amount in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]


def _profile_user(user_row):
    """Identity card for the signed-in user.

    `created_at` is `datetime('now')` TEXT — space-separated, not ISO
    `T`-separated, so it needs `datetime.fromisoformat`, not `date`. It carries
    a DEFAULT but no NOT NULL, so a hand-inserted row can hold NULL.
    """
    name = user_row["name"]
    raw = user_row["created_at"]
    return {
        "name": name,
        "email": user_row["email"],
        "member_since": (
            datetime.fromisoformat(raw).strftime("%d %B %Y") if raw else "—"
        ),
        "initials": _initials(name),
    }


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

@app.route("/profile")
@login_required
def profile():
    """Render the signed-in user's own profile page from the database.

    One query supplies the rows, and every figure on the page is derived from
    that single sequence by the helpers above, so no value can drift from the
    rows it summarises. Both queries are scoped by `session["user_id"]`; no
    expense id, user id or email is ever taken from the request.
    """
    user_id = session["user_id"]  # read once, so the two queries cannot disagree
    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user_row is None:
            # The session points at an account that no longer exists. Drop it
            # rather than rendering a page that greets None.
            session.clear()
            return redirect(url_for("login"))

        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses"
            " WHERE user_id = ? ORDER BY date DESC, id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    # Built once and handed to both the template and _profile_stats, so the
    # "top category" stat always names the same category as the tallest bar.
    # `rows` here are raw database rows — _profile_stats sums their `amount`,
    # so it must not be given the inr()-formatted list from _profile_expenses.
    breakdown = _profile_breakdown(rows)

    return render_template(
        "profile.html",
        user=_profile_user(user_row),
        stats=_profile_stats(rows, breakdown),
        expenses=_profile_expenses(rows),
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
