from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request

from env import load_dotenv
from storage import ReportStore, SubjectStore, now_iso


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
DATA_FILE = os.getenv("DATA_FILE", str(BASE_DIR / "backend" / "data" / "reports.json"))
SUBJECTS_FILE = os.getenv("SUBJECTS_FILE", str(BASE_DIR / "backend" / "data" / "subjects.json"))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "1") == "1"

FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
def resolve_data_path(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return p


store = ReportStore(resolve_data_path(DATA_FILE))
subject_store = SubjectStore(resolve_data_path(SUBJECTS_FILE))

ALLOWED_CATEGORIES = {"safety", "harassment", "policy", "other"}
ALLOWED_STATUSES = {"new", "in_progress", "resolved", "rejected"}
STATUS_ALIASES = {
    "in progress": "in_progress",
    "in-progress": "in_progress",
    "inprogress": "in_progress",
    "triaged": "in_progress",
}


def canonical_status(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in STATUS_ALIASES:
        return STATUS_ALIASES[v]
    return v.replace("-", "_").replace(" ", "_")


def report_subject_label(report: dict) -> str:
    return str(report.get("subject_label") or report.get("subject") or "").strip()


def filter_reports(reports: list[dict]) -> list[dict]:
    """Filter reports using query params.

    Supported query params (admin-only endpoints):
    - status
    - category
    - subject_id
    - q (searches id, subject label, description)
    """

    status_q = canonical_status(request.args.get("status", "")).strip()
    category_q = str(request.args.get("category", "")).strip().lower()
    subject_id_q = str(request.args.get("subject_id", "")).strip()
    q = str(request.args.get("q", "")).strip().lower()

    out: list[dict] = []
    for r in reports:
        if status_q and canonical_status(str(r.get("status", ""))) != status_q:
            continue
        if category_q and str(r.get("category", "")).strip().lower() != category_q:
            continue
        if subject_id_q and str(r.get("subject_id", "")).strip() != subject_id_q:
            continue
        if q:
            hay = " ".join(
                [
                    str(r.get("id", "")),
                    report_subject_label(r),
                    str(r.get("description", "")),
                ]
            ).lower()
            if q not in hay:
                continue
        out.append(r)

    return out


def json_error(message: str, status: int = 400, **extra):
    payload: dict[str, object] = {"ok": False, "error": message}
    if extra:
        payload["details"] = extra
    return jsonify(payload), status


def is_admin_request() -> bool:
    token = request.headers.get("X-Admin-Token", "")
    return bool(ADMIN_TOKEN) and token == ADMIN_TOKEN


@app.errorhandler(404)
def not_found(_):
    return json_error("Not found", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return json_error("Method not allowed", 405)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "status": "ok"})


@app.route("/api/reports", methods=["POST"])
def create_report():
    payload = request.get_json(silent=True) or {}

    subject_id = str(payload.get("subject_id", "")).strip()
    description = str(payload.get("description", "")).strip()
    category = str(payload.get("category", "other")).strip().lower() or "other"
    incident_date = str(payload.get("incident_date", "")).strip()
    location = str(payload.get("location", "")).strip()
    evidence_url = str(payload.get("evidence_url", "")).strip()
    reporter_contact = str(payload.get("reporter_contact", "")).strip()

    errors: dict[str, str] = {}

    if not subject_id:
        errors["subject_id"] = "Select a person/subject from the list."
    else:
        subject = subject_store.get(subject_id)
        if not subject or subject.get("active", True) is not True:
            errors["subject_id"] = "Unknown or inactive subject."

    if not (10 <= len(description) <= 4000):
        errors["description"] = "Description must be 10-4000 characters."

    if category not in ALLOWED_CATEGORIES:
        errors["category"] = f"Category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}."

    if incident_date:
        try:
            date.fromisoformat(incident_date)
        except ValueError:
            errors["incident_date"] = "Incident date must be YYYY-MM-DD."

    if location and len(location) > 200:
        errors["location"] = "Location must be at most 200 characters."

    if evidence_url and len(evidence_url) > 500:
        errors["evidence_url"] = "Evidence URL must be at most 500 characters."

    if reporter_contact and len(reporter_contact) > 200:
        errors["reporter_contact"] = "Contact must be at most 200 characters."

    if errors:
        return json_error("Validation error", 400, fields=errors)

    subject = subject_store.get(subject_id)
    subject_label = str((subject or {}).get("display_name", "")).strip() or subject_id

    report = {
        "id": uuid.uuid4().hex,
        "created_at": now_iso(),
        "updated_at": None,
        "status": "new",
        "subject_id": subject_id,
        "subject_label": subject_label,
        # Backward compatible field name (older UI uses this)
        "subject": subject_label,
        "category": category,
        "description": description,
        "incident_date": incident_date or None,
        "location": location or None,
        "evidence_url": evidence_url or None,
        "reporter_contact": reporter_contact or None,
        "internal_notes": None,
    }

    store.add(report)

    # Minimal receipt (avoid echoing content back)
    return jsonify({"ok": True, "report": {"id": report["id"], "created_at": report["created_at"]}}), 201


@app.route("/api/reports", methods=["GET"])
def list_reports():
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    reports = filter_reports(store.list())
    reports.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    # Basic pagination
    try:
        limit = int(request.args.get("limit", "200"))
    except ValueError:
        limit = 200
    try:
        offset = int(request.args.get("offset", "0"))
    except ValueError:
        offset = 0

    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    total = len(reports)
    page = reports[offset : offset + limit]
    return jsonify({"ok": True, "reports": page, "total": total, "limit": limit, "offset": offset})


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_report(report_id: str):
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    report = store.get(report_id)
    if not report:
        return json_error("Not found", 404)

    return jsonify({"ok": True, "report": report})


@app.route("/api/reports/<report_id>", methods=["PATCH"])
def update_report(report_id: str):
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    payload = request.get_json(silent=True) or {}

    updates: dict[str, object] = {}

    if "status" in payload:
        status = canonical_status(str(payload.get("status", "")))
        if status not in ALLOWED_STATUSES:
            return json_error(
                "Validation error",
                400,
                fields={"status": f"Status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}."},
            )
        updates["status"] = status

    if "internal_notes" in payload:
        notes = str(payload.get("internal_notes", "")).strip()
        if len(notes) > 4000:
            return json_error("Validation error", 400, fields={"internal_notes": "Max 4000 characters."})
        updates["internal_notes"] = notes or None

    if not updates:
        return json_error("Validation error", 400, fields={"_": "No updatable fields provided."})

    updated = store.update(report_id, updates)
    if not updated:
        return json_error("Not found", 404)

    return jsonify({"ok": True, "report": updated})


@app.route("/api/reports/<report_id>/status", methods=["GET"])
def get_report_status(report_id: str):
    """Public endpoint to check status using a report reference id."""

    report = store.get(report_id)
    if not report:
        return json_error("Not found", 404)

    return jsonify(
        {
            "ok": True,
            "report": {
                "id": report.get("id"),
                "created_at": report.get("created_at"),
                "updated_at": report.get("updated_at"),
                "status": canonical_status(str(report.get("status", "new"))) or "new",
            },
        }
    )


@app.route("/api/reports/export.csv", methods=["GET"])
def export_reports_csv():
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    reports = filter_reports(store.list())
    reports.sort(key=lambda r: r.get("created_at") or "", reverse=True)

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "updated_at",
            "status",
            "category",
            "subject_id",
            "subject_label",
            "incident_date",
            "location",
            "evidence_url",
            "reporter_contact",
            "description",
            "internal_notes",
        ]
    )

    for r in reports:
        writer.writerow(
            [
                r.get("id"),
                r.get("created_at"),
                r.get("updated_at"),
                canonical_status(str(r.get("status", "new"))) or "new",
                r.get("category"),
                r.get("subject_id"),
                report_subject_label(r),
                r.get("incident_date"),
                r.get("location"),
                r.get("evidence_url"),
                r.get("reporter_contact"),
                r.get("description"),
                r.get("internal_notes"),
            ]
        )

    csv_text = output.getvalue()
    return (
        csv_text,
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=reports.csv",
        },
    )


@app.route("/api/subjects", methods=["GET", "POST"])
def subjects_collection():
    if request.method == "GET":
        q = str(request.args.get("q", "")).strip().lower()
        subjects = subject_store.list(include_inactive=False)
        if q:
            subjects = [
                s
                for s in subjects
                if q
                in (" ".join([str(s.get("display_name", "")), str(s.get("code", ""))]).lower())
            ]
        subjects.sort(key=lambda s: str(s.get("display_name", "")).lower())
        public = [
            {"id": s.get("id"), "display_name": s.get("display_name"), "code": s.get("code")}
            for s in subjects
            if s.get("id") and s.get("display_name")
        ]
        return jsonify({"ok": True, "subjects": public})

    # POST
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    payload = request.get_json(silent=True) or {}
    display_name = str(payload.get("display_name", "")).strip()
    code = str(payload.get("code", "")).strip() or None

    fields: dict[str, str] = {}
    if not (2 <= len(display_name) <= 120):
        fields["display_name"] = "Display name must be 2-120 characters."
    if code and len(code) > 50:
        fields["code"] = "Code must be at most 50 characters."

    if code:
        existing = [s for s in subject_store.list(include_inactive=True) if str(s.get("code", "")).strip() == code]
        if existing:
            fields["code"] = "Code must be unique."

    if fields:
        return json_error("Validation error", 400, fields=fields)

    subject = {
        "id": uuid.uuid4().hex,
        "created_at": now_iso(),
        "updated_at": None,
        "active": True,
        "display_name": display_name,
        "code": code,
    }
    subject_store.add(subject)
    return jsonify({"ok": True, "subject": subject}), 201


@app.route("/api/subjects/all", methods=["GET"])
def subjects_all():
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    subjects = subject_store.list(include_inactive=True)
    subjects.sort(key=lambda s: (str(s.get("active", True)) != "True", str(s.get("display_name", "")).lower()))
    return jsonify({"ok": True, "subjects": subjects})


@app.route("/api/subjects/<subject_id>", methods=["PATCH"])
def subjects_update(subject_id: str):
    if not is_admin_request():
        return json_error("Unauthorized", 401)

    payload = request.get_json(silent=True) or {}
    updates: dict[str, object] = {}
    fields: dict[str, str] = {}

    if "display_name" in payload:
        display_name = str(payload.get("display_name", "")).strip()
        if not (2 <= len(display_name) <= 120):
            fields["display_name"] = "Display name must be 2-120 characters."
        else:
            updates["display_name"] = display_name

    if "code" in payload:
        code = str(payload.get("code", "")).strip() or None
        if code and len(code) > 50:
            fields["code"] = "Code must be at most 50 characters."
        else:
            if code:
                existing = [
                    s
                    for s in subject_store.list(include_inactive=True)
                    if s.get("id") != subject_id and str(s.get("code", "")).strip() == code
                ]
                if existing:
                    fields["code"] = "Code must be unique."
                else:
                    updates["code"] = code
            else:
                updates["code"] = None

    if "active" in payload:
        active = payload.get("active")
        if not isinstance(active, bool):
            fields["active"] = "Active must be true/false."
        else:
            updates["active"] = active

    if fields:
        return json_error("Validation error", 400, fields=fields)
    if not updates:
        return json_error("Validation error", 400, fields={"_": "No updatable fields provided."})

    updated = subject_store.update(subject_id, updates)
    if not updated:
        return json_error("Not found", 404)

    return jsonify({"ok": True, "subject": updated})


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
