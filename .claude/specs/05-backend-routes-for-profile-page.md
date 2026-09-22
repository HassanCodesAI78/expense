# Spec: Backend Routes for Profile Page

## Overview

Step 4 built `/profile` as a fully designed page whose every value — the user's
name and email, the member-since date, the transaction rows, the three summary
stats, and the category breakdown — is hardcoded Python in `app.py`
(`PROFILE_USER`, `PROFILE_EXPENSES`). This step replaces those literals with real
SQLite reads so the page shows the **signed-in user's own** data. The rendered
output for the seeded demo user must not change: Step 4 derived every figure from
`PROFILE_EXPENSES` specifically so the swap could happen without the page looking
different, and that is the test of whether this step is done correctly.

The work is confined to `app.py`. The template and stylesheet built in Step 4 are
already shaped to receive this data and are not expected to change.

## Depends on

- **Step 1 — Database setup.** `get_db()`, and the `users` / `expenses` tables.
- **Step 2 — Registration.** Accounts must exist to sign in as.
- **Step 3 — Login and Logout.** `session["user_id"]` must be set on login.
- **Step 4 — Profile Page.** This step *modifies* Step 4's work; it cannot be
  implemented without it.

> **Sequencing note — read before implementing.** Step 4 is committed to the
> branch `feature/profile-page-design` (commits `824bf16`, `4c2cda4`) and is **not
> merged into `main`**. `main` still carries the stub
> `@app.route("/profile")` → `return "Profile page — coming in Step 4"`. Step 4
> must be merged to `main` and this branch rebased on it before any of the
> template-context work below is possible. The `login()`/`register()` changes this
> step builds on (`SELECT id, name, password_hash`, and the `session["user_name"]`
> assignment) also exist only on that branch.

## Routes

No new routes. One existing route changes behaviour:

- `GET /profile` — render the profile page from database queries — logged-in only.
  The route and its `@login_required` decorator are added by Step 4; this step
  replaces only the function body.

## Database changes

No database changes. The existing schema is sufficient and this step is
read-only — no `INSERT`, `UPDATE`, or `DELETE` is issued.

| Table | Columns read | Used for |
| --- | --- | --- |
| `users` | `name`, `email`, `created_at` | Identity card: name, email, member-since |
| `expenses` | `amount`, `category`, `date`, `description` | Transaction table, summary stats, breakdown |

## Templates

- **Create:** none.
- **Modify:** `templates/profile.html` — **only if** Step 4's template turns out
  to assume at least one expense row (for example an unconditional
  `breakdown[0]`). A newly registered user has zero expenses, so an empty state
  is required for the transaction table, the stats row, and the breakdown. If
  Step 4 already renders these sections over empty sequences without error, make
  no change. Confirm by testing with a fresh account before editing.

## Files to change

- `app.py` — replace the body of `profile()` and delete the `PROFILE_USER` and
  `PROFILE_EXPENSES` literals.

## Files to create

None.

## New dependencies

No new dependencies. `sqlite3` (standard library) via the existing `get_db()`, plus
`datetime.date` for the member-since format. Flask and Werkzeug are already pinned.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — `?` placeholders, never string formatting or f-strings in SQL
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- **Scope every query by the session user.** `WHERE user_id = ?` with
  `session["user_id"]`, bound as a parameter. No expense id, user id, or email may
  ever be accepted from the request — `url_for` and the browser are not trusted.
  This route takes no arguments, and it must stay that way.
- **Read `session["user_id"]` once** into a local at the top of the function and
  reuse it, so the two to three queries cannot disagree.
- **Handle a stale session.** If the `users` row for `session["user_id"]` no longer
  exists, `session.clear()` and `redirect(url_for("login"))` — do not render a page
  greeting `None`, and do not raise on the missing row.
- **Handle an empty account.** A user with no expenses must render a valid page:
  a zero total, a zero count, no top category, and an empty breakdown and table.
  Guard the existing `breakdown[0]` access rather than letting it raise
  `IndexError`.
- **Derive every figure from the rows, as Step 4 did.** Total, count, top category,
  and each bar width must come from the same result set the table renders. Do not
  add a second source of truth, and do not compute a total in SQL while computing
  the breakdown in Python if that risks the two disagreeing.
- **Format amounts with the existing `inr()` helper** (`app.py`), never in the
  template — Jinja has no thousands separator and templates must not do arithmetic.
- **Order expenses newest first**, `ORDER BY date DESC, id DESC`. The `id`
  tiebreaker keeps same-day rows in a stable order across requests.
- **Format `users.created_at` for display.** It is stored by `datetime('now')` as
  `YYYY-MM-DD HH:MM:SS`; Step 4's page shows `18 September 2026`. Parse with
  **`datetime.fromisoformat()`** and format with **`%d %B %Y`**. Confirm the exact
  string Step 4 produced is reproduced.
    - **Use `datetime.fromisoformat`, not `date.fromisoformat`.** The two parsers
      look interchangeable and are not: `date.fromisoformat('2026-09-18 12:11:47')`
      raises `ValueError`, because the stored value is space-separated and carries a
      time component. The expense rows use `date.fromisoformat` on a bare
      `YYYY-MM-DD`; `created_at` needs `datetime`. Both calls appear ten lines apart
      — get the pairing right.
    - **Do not use `%-d`.** It is a glibc extension and raises
      `ValueError: Invalid format string` on Windows, which would 500 `/profile` for
      every user. `%#d` is the Windows equivalent and breaks the mirror-image way on
      Linux. Use plain `%d`; `18` is unaffected, and a single-digit day renders
      zero-padded (`05 September 2026`) rather than unpadded. That padding is the
      deliberate trade for portability — do not "fix" it.
- **Close connections in a `finally` block**, following `database/db.py`'s pattern
  and the existing `register()` / `login()` implementations.
- Keep the endpoint function name `profile` — `base.html` calls
  `url_for('profile')`, and the navbar link to it is added in Step 4.
- **Do not change the navbar's data source.** `base.html` reads
  `session.get('user_name')`, which Step 4 caches at login to avoid a query on
  every page render. Reading the name from the database here and leaving the
  session copy untouched is correct; removing the session copy is not in scope.

## Definition of done

- [ ] `python app.py` starts with no errors and serves on port 5001
- [ ] `PROFILE_USER` and `PROFILE_EXPENSES` no longer exist in `app.py`
- [ ] Visiting `/profile` while signed out redirects to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` and visiting `/profile` returns HTTP 200
- [ ] The page renders **exactly** as it did in Step 4 — same name, email, member-since
      date, total, transaction count, top category, row count, and bar widths. Every
      one of those figures must now come from the database
- [ ] The name and email shown belong to the signed-in user, proven by registering a
      second account with a different name and confirming `/profile` shows that one
- [ ] The transaction table matches the Step 4 output row for row, newest first
- [ ] The summary total equals the sum of the amounts displayed in the table — verify
      by hand **for the demo user only** (₹9,747 across 8 whole-rupee rows).
      Known limitation, inherited from Step 4 and out of scope here: `inr()` rounds
      each amount independently, so for an account holding paise the printed total
      can differ from the sum of the printed rows by ₹1. Reachable today — the
      local DB's `vikram.gehlot962@rediffmail.com` has four such rows (displayed
      rows sum to ₹3,806; the total prints ₹3,807). Do **not** "fix" this by making
      the total the sum of the *rounded* rows — that would make the headline figure
      disagree with the data. Fixing it properly means rendering paise, which would
      change Step 4's visual output.
- [ ] The category breakdown lists every category the user has expenses in, and the
      percentages sum to 100 (allowing rounding)
- [ ] A freshly registered account with no expenses renders `/profile` with a zero
      total, a zero count, and no `IndexError` traceback
- [ ] Adding a row directly to `expenses` for the signed-in user and reloading
      `/profile` reflects it — proving the page is not cached or hardcoded
- [ ] An expense belonging to a *different* user never appears in this user's table,
      total, or breakdown
- [ ] Manually setting `session["user_id"]` to a non-existent id redirects to
      `/login` rather than raising
- [ ] No SQL string formatting is used anywhere in the new code — every bound value
      goes through a `?` placeholder
