import json
import sqlite3
import threading
from typing import List


class Storage:
    """Thread-safe SQLite-backed user preference storage."""

    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    macro    TEXT NOT NULL DEFAULT '[]',
                    branches TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_user_prefs(self, user_id: int) -> dict[str, list]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT macro, branches FROM user_prefs WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT OR IGNORE INTO user_prefs (user_id) VALUES (?)",
                    (user_id,),
                )
                conn.commit()
                return {"macro": [], "branches": []}
            return {
                "macro": json.loads(row[0]),
                "branches": json.loads(row[1]),
            }

    def toggle_macro(self, user_id: int, macro: str) -> dict:
        prefs = self.get_user_prefs(user_id)
        if macro in prefs["macro"]:
            prefs["macro"].remove(macro)
        else:
            prefs["macro"].append(macro)
        self._save(user_id, prefs)
        return prefs

    def toggle_branch(self, user_id: int, branch: str) -> dict:
        prefs = self.get_user_prefs(user_id)
        if branch in prefs["branches"]:
            prefs["branches"].remove(branch)
        else:
            prefs["branches"].append(branch)
        self._save(user_id, prefs)
        return prefs

    def set_all_macro(self, user_id: int, macros: List[str]) -> dict:
        prefs = self.get_user_prefs(user_id)
        prefs["macro"] = list(macros)
        self._save(user_id, prefs)
        return prefs

    def set_all_branches(self, user_id: int, branches: List[str]) -> dict:
        prefs = self.get_user_prefs(user_id)
        prefs["branches"] = list(branches)
        self._save(user_id, prefs)
        return prefs

    def reset_user_prefs(self, user_id: int) -> dict:
        empty: dict = {"macro": [], "branches": []}
        self._save(user_id, empty)
        return empty

    def list_users(self) -> List[int]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM user_prefs").fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save(self, user_id: int, prefs: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_prefs (user_id, macro, branches)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    macro    = excluded.macro,
                    branches = excluded.branches
                """,
                (
                    user_id,
                    json.dumps(prefs["macro"]),
                    json.dumps(prefs["branches"]),
                ),
            )
            conn.commit()
