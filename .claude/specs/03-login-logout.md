# Spec: Login and Logout

## Overview

Make signing in and signing out actually work. Registration (step 02) creates
accounts and starts a session, but once that session ends there is no way back
into the account, and no way to end it deliberately. Today `/login` renders
`login.html` but the route is GET-only, so the form's POST is rejected; `/logout`
returns the string "Logout — coming in Step 3" and touches no session at all.
This step verifies submitted credentials against the stored Werkzeug hash,
starts a session on success, and clears that session on logout. It also makes
the shared navbar session-aware — the piece step 02 explicitly deferred — so the
"Sign in" and "Get started" links finally reflect who is signed in.

## Depends on

**Step 02 — Registration.** This step assumes:

- Password hashes were written by `generate_password_hash()`; login verifies them
  with `check_password_hash()`. The two must be the same scheme.
- The email normalisation rule (`.strip().lower()`) from step 02. Login must apply
  the **identical** rule, or an account created as `Foo@Example.com` (stored
  lowercase) cannot be signed into.
- `session["user_id"]` is the established session key.
- `app.secret_key` is set. Flask raises `RuntimeError` on any session read *or*
  write without it. If step 02 has not landed yet, this step must set it before
  anything else works.

**Step 01 — Database setup** for `get_db()` and the `users` table.

## Routes

- `GET /login` — render the sign-in form — public
- `POST /login` — verify credentials, start a session, redirect — public
- `GET /logout` — clear the session, redirect — logged-in (safe to call while logged out)

`@app.route("/login")` must gain `methods=["GET", "POST"]`, or Flask answers the
form's POST with 405. `@app.route("/logout")` keeps its path and endpoint name
but replaces the placeholder body.

Both successful login and logout redirect to `url_for("landing")` (`/`),
consistent with step 02. A later step should repoint the post-login redirect
once a real profile or dashboard page exists.

Logout uses `GET` so the navbar can render it as a plain link. A `POST`-only
logout with a form button is the more defensible choice against link prefetching,
but this project has no CSRF protection anywhere, so `GET` keeps it consistent
with the rest of the stack. Worth revisiting if CSRF protection is ever added.

## Database changes

No database changes. Login only reads columns that already exist in `users`, and
logout touches no database at all:

| Column | Read for |
| --- | --- |
| id | Written to `session["user_id"]` |
| email | Looked up by the normalised submitted address |
| password_hash | Passed to `check_password_hash()` |

No `last_login` column, and no session table — Flask's signed cookie session is
sufficient here.

## Templates

- **Create:** none.
- **Modify:** `templates/base.html` — the navbar becomes session-aware. This is
  the deferral from step 02, now in scope. Branch the `.nav-links` block on
  `session.get('user_id')`: when set, show a "Sign out" link to
  `url_for('logout')`; when unset, keep the existing "Sign in" and "Get started"
  links. Reuse the existing `.nav-links` and `.nav-cta` classes — no new CSS.
  Showing the user's *name* in the navbar is out of scope; it would require a
  database read on every page render.
- **Modify:** `templates/login.html` — retain the submitted email after a failed
  attempt with `value="{{ email or '' }}"`, matching what step 02 does for
  `register.html`. Do not repopulate the password field. The existing
  `{% if error %}` block already renders the message and needs no change.

## Files to change

- `app.py` — import `session`; convert `login` to GET+POST and implement it;
  replace the `logout` placeholder body; confirm `app.secret_key` is set.
- `templates/base.html` — session-aware navbar.
- `templates/login.html` — retain email on failure.

No CSS file changes. Every class involved already exists in
`static/css/style.css`.

## Files to create

None.

## New dependencies

No new dependencies. Standard library only (`sqlite3`, `os`), plus `flask` and
`werkzeug`, both already pinned in `requirements.txt`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — `?` placeholders, never string formatting or f-strings in SQL
- Passwords verified with werkzeug: `check_password_hash()` from `werkzeug.security`, never a plaintext comparison
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- **Never reveal whether an account exists.** An unknown email and a wrong
  password must produce the *identical* message ("Invalid email or password.").
  Distinct messages let an attacker enumerate registered addresses, which is
  exactly what this app's real user emails would leak.
- **Normalise the email identically to registration:** `.strip().lower()` before
  the lookup. Divergence here silently breaks mixed-case accounts.
- **Guard the lookup.** If no row matches, do not call `check_password_hash()` on
  `None` — return the generic error immediately.
- **Clear before setting.** Call `session.clear()` on successful login, then set
  `session["user_id"]`, so no stale session data survives. On logout call
  `session.clear()`.
- **Validate only that both fields are non-empty.** Do not enforce the 8-character
  minimum at login — it leaks the password policy and would lock out any account
  whose password predates the rule.
- **Never log, print, or echo the submitted password**, and never render it back
  into the form.
- Close connections in a `finally` block, following `database/db.py`.
- Keep the endpoint function names `login` and `logout` — `base.html`,
  `register.html`, and `login.html` call `url_for('login')`, and the navbar will
  call `url_for('logout')`. Renaming breaks templates in other files.
- **No `login_required` decorator in this step.** It is out of scope here and
  belongs with the first page that needs protecting (profile, step 4).
- `/logout` must not error when no session exists — redirect to `/` regardless.

## Definition of done

- [ ] `python app.py` starts with no errors and serves on port 5001
- [ ] `GET /login` returns 200 and renders the sign-in form
- [ ] Submitting valid credentials redirects to `/` and shows no 405
- [ ] The signed-in navbar then shows "Sign out" instead of "Sign in" / "Get started",
      confirming the session persisted across a request
- [ ] Submitting a correct email with the wrong password re-renders the form with
      an error and starts no session
- [ ] Submitting an unregistered email produces the **exact same** error text as
      the wrong-password case
- [ ] Submitting a known email in different case (`FOO@Example.com`) signs in
      successfully
- [ ] Submitting with a blank email or password re-renders with an error
- [ ] `GET /logout` clears the session, redirects to `/`, and the navbar reverts to
      "Sign in" / "Get started"
- [ ] `GET /logout` while already logged out redirects to `/` without erroring
- [ ] After logout, revisiting `/login` and re-authenticating succeeds, proving the
      session was cleared rather than corrupted
- [ ] The submitted password appears nowhere in the database, the logs, or the
      re-rendered HTML
- [ ] Existing registration behaviour from step 02 still works unchanged
