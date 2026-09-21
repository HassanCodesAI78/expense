import os
import sqlite3

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


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
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
                    return redirect(url_for("landing"))
        finally:
            conn.close()

    return render_template("register.html", error=error, name=name, email=email)


@app.route("/login", methods=["GET", "POST"])
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
                "SELECT id, password_hash FROM users WHERE email = ?", (email,)
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
def profile():
    return "Profile page — coming in Step 4"


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
