"""
Audit Log
---------
Append-only record of every decision made by every agent, for every incident.
No update or delete operations exist on purpose -- once a decision is logged,
it cannot be altered. This is the core of "explainability": for any action the
system takes, you can trace back exactly which agent decided it, what evidence
it used, and when.

PERFORMANCE NOTE (see Decision 011 in ARCHITECTURE_DECISIONS.md): this class
keeps ONE persistent connection open for the object's lifetime, instead of
opening/closing a new SQLite connection on every log() call. The earlier
per-call-connection version measured ~22ms/record under batch load -- almost
all of it connection overhead, not actual pipeline work. This fix cut that
dramatically (see architecture doc for the before/after numbers).
"""
import sqlite3
import json
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "audit_log.db")


class AuditLog:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                evidence TEXT NOT NULL,
                outcome TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def log(self, incident_id: str, agent: str, action: str, evidence: dict, outcome: str):
        self.conn.execute(
            "INSERT INTO audit_events (incident_id, timestamp, agent, action, evidence, outcome) VALUES (?, ?, ?, ?, ?, ?)",
            (incident_id, time.time(), agent, action, json.dumps(evidence), outcome)
        )
        self.conn.commit()

    def get_incident_trail(self, incident_id: str):
        cur = self.conn.execute(
            "SELECT timestamp, agent, action, evidence, outcome FROM audit_events WHERE incident_id = ? ORDER BY timestamp ASC",
            (incident_id,)
        )
        rows = cur.fetchall()
        return [
            {"timestamp": r[0], "agent": r[1], "action": r[2], "evidence": json.loads(r[3]), "outcome": r[4]}
            for r in rows
        ]

    def close(self):
        self.conn.close()
