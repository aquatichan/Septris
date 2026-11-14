"""Transactional local replay store for the SEPTRIS prototype.

Raw observations remain in this local SQLite file solely to make an individual
replay deterministic. Audit rows contain keyed hashes, never raw payloads.
This is not production EHR storage.
"""

import hashlib
import hmac
import json
import os
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
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    patient_id TEXT NOT NULL,
                    hospital TEXT NOT NULL CHECK(hospital IN ('A', 'B')),
                    icu_hour INTEGER NOT NULL CHECK(icu_hour >= 0),
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (patient_id, icu_hour)
                );
                CREATE TABLE IF NOT EXISTS scores (
                    patient_id TEXT PRIMARY KEY,
                    hospital TEXT NOT NULL CHECK(hospital IN ('A', 'B')),
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
            row = con.execute("SELECT value FROM metadata WHERE key='audit_hmac_key'").fetchone()
            if row is None:
                con.execute("INSERT INTO metadata(key, value) VALUES (?, ?)",
                            ("audit_hmac_key", os.urandom(32).hex()))
                self._audit_key = con.execute(
                    "SELECT value FROM metadata WHERE key='audit_hmac_key'"
                ).fetchone()["value"]
            else:
                self._audit_key = row["value"]

    def _hash(self, value: str) -> str:
        return hmac.new(bytes.fromhex(self._audit_key), value.encode(), hashlib.sha256).hexdigest()

    def validate_append(self, payload: dict):
        """Reject mutation, cross-hospital identity switches, and time reversal."""
        with self.connect() as con:
            rows = con.execute(
                "SELECT hospital, icu_hour FROM observations WHERE patient_id=? ORDER BY icu_hour",
                (payload["patient_id"],),
            ).fetchall()
        if not rows:
            return
        if rows[0]["hospital"] != payload["hospital"]:
            raise ValueError("patient_id is already bound to a different source hospital")
        latest = rows[-1]["icu_hour"]
        if payload["icu_hour"] <= latest:
            raise ValueError("ICU hour must be strictly newer than the stored patient history")

    def append_observation(self, payload: dict):
        self.validate_append(payload)
        with self.connect() as con:
            con.execute(
                "INSERT INTO observations VALUES (?, ?, ?, ?, ?)",
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

    def has_patient(self, patient_id: str) -> bool:
        with self.connect() as con:
            return con.execute("SELECT 1 FROM observations WHERE patient_id=? LIMIT 1", (patient_id,)).fetchone() is not None

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
        if not self.has_patient(patient_id):
            raise ValueError("cannot review an unknown patient")
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
        return 0 <= (now - then).total_seconds() < snooze_hours * 3600

    def _audit(self, con, event_type: str, patient_id: str, payload: dict, model_version: str | None = None):
        con.execute(
            "INSERT INTO audit_events(event_type, patient_id_hash, payload_hash, model_version) VALUES (?, ?, ?, ?)",
            (event_type, self._hash(patient_id), self._hash(json.dumps(payload, sort_keys=True)), model_version),
        )
