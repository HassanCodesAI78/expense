# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Spendly — a Flask expense tracker built in numbered stages. Much of the codebase is deliberately a stub: `app.py` carries placeholder routes annotated "coming in Step 3/4/7/8/9", `database/db.py` is a comment listing the three functions to write, and `static/js/main.js` is a single comment line. Work usually means filling in one of those stages rather than restructuring what already exists. There is no README.

## Commands

```bash
pip install -r requirements.txt
python app.py     # dev server at http://127.0.0.1:5001 — note the port, not Flask's default 5000
pytest            # pytest and pytest-flask are installed, but no test suite, conftest, or pytest config exists yet
```

No build step, linter, formatter, or CI. `static/` is served directly by Flask — there is no `package.json`, npm, or JS tooling anywhere.

## Architecture

**Routing.** All routes live in `app.py` as a flat list, split by a banner comment into real pages (top) and unimplemented stage placeholders (bottom). Endpoint function names are load-bearing: `templates/base.html` and the auth pages call `url_for('landing')`, `url_for('login')`, and `url_for('register')`, so renaming a route function breaks templates in other files.

**Templates.** `templates/base.html` is the only layout; pages extend it and fill `{% block title %}`, `{% block head %}`, `{% block content %}`, `{% block scripts %}`. The navbar and footer exist only in base.html — no page defines its own footer, so the footer links (Terms, Privacy) are edited there, not in `landing.html`.

**Auth forms run ahead of the backend.** `register.html` and `login.html` POST to `/register` and `/login`, and both render `{% if error %}` — but those routes are currently GET-only and pass no `error`. The templates are the spec for the auth step; don't quietly "fix" the mismatch without implementing the route.

**Database.** `database/db.py` is specified by its own comment: `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()`, `seed_db()`. The database file is named `expense_tracker.db` at the repo root — that name comes from `.gitignore`, the only place it is fixed so far.

## Styling

One stylesheet, `static/css/style.css`. There is no `landing.css` and no per-page CSS; page-specific rules live in that file under banner comments (`/* Hero */`, `/* Legal pages (terms, privacy) */`, …).

- Design tokens are CSS custom properties in `:root`: `--ink*` for text, `--paper*` for backgrounds, `--accent` (green) / `--accent-2` (amber), `--font-display` (DM Serif Display) / `--font-body` (DM Sans), `--max-width`, `--radius-*`.
- The hero scopes its own `--hero-*` properties on `.hero` so its brighter green doesn't leak into the rest of the site — follow that pattern for new sections with their own palette.
- Legal pages reuse landing section classes instead of new ones: `terms.html` and `privacy.html` are assembled from `.features` / `.feature-title` / `.feature-body` plus `.legal-inner` and `.legal-section`.
- `base.html` loads DM Sans at weights 300–600 only. To use 700, add the weight via a page's `{% block head %}` (as `landing.html` does) rather than editing the shared font link.
- Global button rules are generic: `.btn-ghost:hover` and `.btn-primary` set colors that a restyled section must override at equal-or-higher specificity. The hero does this with `.hero-actions .btn-primary` / `.hero-actions .btn-ghost`.

**JavaScript** is vanilla and framework-free by project constraint (no libraries, no dependencies). `main.js` is loaded on every page; page-specific behavior belongs in that page's `{% block scripts %}`, as the video modal in `landing.html` does.

## Conventions

- Copy is India-facing — amounts use ₹, and auth form placeholders use Indian names and addresses.
- Both Python and CSS separate sections with a full-width banner comment (`# ---- #` / `/* ---- */`). Indentation is 4 spaces throughout.
