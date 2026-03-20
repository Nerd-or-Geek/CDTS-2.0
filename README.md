# Reporting System (Flask + JSON + HTML/CSS)

This is a lightweight reporting system:
- **Backend**: Python + Flask JSON API
- **Storage**: local JSON file (no database)
- **Frontend**: HTML/CSS/JS (served by Flask)

> Privacy note: This demo is intentionally minimal. Avoid submitting sensitive personal info (addresses, phone numbers, IDs, etc.).

## Run locally (Windows)

1) Create/activate a virtual environment

2) Install deps
- Requirements are in `backend/requirements.txt`

3) Start the server
- Run `backend/app.py`

4) Open in your browser
- http://127.0.0.1:5000

## Admin access

Admin endpoints require `ADMIN_TOKEN` (see `.env`).
- Admin page: http://127.0.0.1:5000/admin.html

Admin API:
- `GET /api/reports` (header: `X-Admin-Token: <token>`)
	- Optional filters: `?q=...&status=...&subject_id=...`
- `GET /api/reports/<id>`
- `PATCH /api/reports/<id>` body: `{ "status": "in_progress", "internal_notes": "..." }`
- `GET /api/reports/export.csv` (same filters, returns a CSV download)

People (subjects) API:
- `GET /api/subjects` (public list for the report form)
- `GET /api/subjects/all` (admin list)
- `POST /api/subjects` (admin create)
- `PATCH /api/subjects/<id>` (admin update)

Public status check:
- `GET /api/reports/<id>/status` (returns only status + timestamps)

## Data storage

Reports are stored in `backend/data/reports.json`.
- The file is **created automatically** on first run.
- It is **gitignored** by default.

Subjects (people list) are stored in `backend/data/subjects.json`.
- The file is **created automatically** when first used.
- It is **gitignored** by default.

## Not for production (yet)

If you want this production-ready, next steps are:
- real auth (sessions/OAuth)
- database (SQLite/Postgres)
- audit logging + rate limiting
- encryption at rest for contact fields
- role-based admin UI
