from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReportStore:
    """A tiny JSON-file backed store.

    Data format: a JSON array of objects.

    This is meant for local demos and small deployments.
    For multi-process / multi-host setups, move to a database.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock = FileLock(str(path) + ".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read_unlocked(self) -> list[dict[str, Any]]:
        self._ensure_file()

        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return []

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Back up the corrupted file and reset.
            backup = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                if backup.exists():
                    backup.unlink()
                self.path.replace(backup)
            except OSError:
                # If we can't move it, we'll just overwrite.
                pass
            self.path.write_text("[]", encoding="utf-8")
            return []

        if not isinstance(data, list):
            return []

        # Keep only dict entries
        return [x for x in data if isinstance(x, dict)]

    def _write_unlocked(self, data: list[dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, report: dict[str, Any]) -> None:
        with self.lock:
            data = self._read_unlocked()
            data.append(report)
            self._write_unlocked(data)

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read_unlocked()

    def get(self, report_id: str) -> dict[str, Any] | None:
        with self.lock:
            for report in self._read_unlocked():
                if report.get("id") == report_id:
                    return report
        return None

    def update_status(self, report_id: str, status: str) -> dict[str, Any] | None:
        return self.update(report_id, {"status": status})

    def update(self, report_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update a report by id.

        Caller is responsible for validating fields.
        """

        with self.lock:
            data = self._read_unlocked()
            for report in data:
                if report.get("id") == report_id:
                    for k, v in updates.items():
                        # Prevent changing identity fields
                        if k in {"id", "created_at"}:
                            continue
                        report[k] = v
                    report["updated_at"] = now_iso()
                    self._write_unlocked(data)
                    return report
        return None


class SubjectStore:
    """JSON-file backed store for report subjects (people).

    Data format: a JSON array of objects.
    """

    def __init__(self, path: Path):
        self.path = path
        self.lock = FileLock(str(path) + ".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read_unlocked(self) -> list[dict[str, Any]]:
        self._ensure_file()

        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return []

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            backup = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                if backup.exists():
                    backup.unlink()
                self.path.replace(backup)
            except OSError:
                pass
            self.path.write_text("[]", encoding="utf-8")
            return []

        if not isinstance(data, list):
            return []

        return [x for x in data if isinstance(x, dict)]

    def _write_unlocked(self, data: list[dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, subject: dict[str, Any]) -> None:
        with self.lock:
            data = self._read_unlocked()
            data.append(subject)
            self._write_unlocked(data)

    def list(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        with self.lock:
            data = self._read_unlocked()
            if include_inactive:
                return data
            return [s for s in data if s.get("active", True) is True]

    def get(self, subject_id: str) -> dict[str, Any] | None:
        with self.lock:
            for subject in self._read_unlocked():
                if subject.get("id") == subject_id:
                    return subject
        return None

    def update(self, subject_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self.lock:
            data = self._read_unlocked()
            for subject in data:
                if subject.get("id") == subject_id:
                    for k, v in updates.items():
                        if k in {"id", "created_at"}:
                            continue
                        subject[k] = v
                    subject["updated_at"] = now_iso()
                    self._write_unlocked(data)
                    return subject
        return None
