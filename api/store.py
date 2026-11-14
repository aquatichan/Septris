"""Small transactional SQLite store for replay/demo use.

This is intentionally local and stores no raw values in the audit table.
Do not treat it as production EHR storage.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class ReplayStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init(self):
        with self.connect() as con:
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS observations (
                    patient_id TEXT NOT NULL,
                    hospital TEXT NOT NULL,
                    icu_hour INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (patient_id, icu_hour)
                );
                CREATE TABLE IF NOT EXISTS scores (
                    patient_id TEXT PRIMARY KEY,
                    hospital TEXT NOT NULL,
                    icu_hour INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    reviewer_hash TEXT NOT NULL,
                    action TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    patient_id_hash TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    model_version TEXT
                );
                """
            )

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def append_observation(self, payload: dict):
        with self.connect() as con:
            prior = con.execute(
                "SELECT MAX(icu_hour) AS hour FROM observations WHERE patient_id=?",
                (payload["patient_id"],),
            ).fetchone()["hour"]
            if prior is not None and payload["icu_hour"] < prior:
                raise ValueError("out-of-order ICU hour; replay must be monotonic per patient")
            con.execute(
                "INSERT OR REPLACE INTO observations VALUES (?, ?, ?, ?, ?)",
                (payload["patient_id"], payload["hospital"], payload["icu_hour"],
                 payload["observed_at"], json.dumps(payload, sort_keys=True)),
            )
            self._audit(con, "observation_ingested", payload["patient_id"], payload)

    def history(self, patient_id: str) -> list[dict]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT payload_json FROM observations WHERE patient_id=? ORDER BY icu_hour",
                (patient_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def save_score(self, score: dict):
        with self.connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO scores VALUES (?, ?, ?, ?, ?)",
                (score["patient_id"], score["hospital"], score["icu_hour"],
                 score["observed_at"], json.dumps(score, sort_keys=True)),
            )
            self._audit(con, "score_created", score["patient_id"], score, score.get("model_version"))

    def candidates(self, hospital: str) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT payload_json FROM scores WHERE hospital=?", (hospital,)).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def record_review(self, patient_id: str, reviewer_id: str, reviewed_at: str, action: str):
        with self.connect() as con:
            con.execute("INSERT INTO reviews(patient_id, reviewed_at, reviewer_hash, action) VALUES (?, ?, ?, ?)",
                        (patient_id, reviewed_at, self._hash(reviewer_id), action))
            self._audit(con, "review_recorded", patient_id,
                        {"reviewed_at": reviewed_at, "action": action})

    def is_snoozed(self, patient_id: str, as_of: str, snooze_hours: int = 12) -> bool:
        with self.connect() as con:
            row = con.execute(
                "SELECT reviewed_at FROM reviews WHERE patient_id=? ORDER BY reviewed_at DESC LIMIT 1",
                (patient_id,),
            ).fetchone()
        if not row:
            return False
        from datetime import datetime, timezone
        now = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        then = datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (now - then).total_seconds() < snooze_hours * 3600

    def _audit(self, con, event_type: str, patient_id: str, payload: dict, model_version: str | None = None):
        con.execute(
            "INSERT INTO audit_events(event_type, patient_id_hash, payload_hash, model_version) VALUES (?, ?, ?, ?)",
            (event_type, self._hash(patient_id), self._hash(json.dumps(payload, sort_keys=True)), model_version),
        )
