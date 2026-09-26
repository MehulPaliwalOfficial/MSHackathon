"""SQLite persistence for users, trips, memory, bookings and notifications."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterator

from config import settings
from app.utils import model_to_data


class Database:
    """Small SQLite repository with JSON payloads for expandable domain data."""

    def __init__(self, path: str | Path | None = None):
        self.path = str(path or settings.sqlite_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            conn = self.connect()
            cur = conn.cursor()
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def initialize(self) -> None:
        with self.cursor() as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, key)
                );

                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    destination TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trip_id TEXT,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trip_id TEXT,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def upsert_user(self, user_id: str, email: str | None = None, name: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users(id, email, name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    email=COALESCE(excluded.email, users.email),
                    name=COALESCE(excluded.name, users.name)
                """,
                (user_id, email, name, now),
            )

    def save_memory(self, user_id: str, key: str, value: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(model_to_data(value), ensure_ascii=False, default=str)
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory(user_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (user_id, key, payload, now),
            )

    def get_memory(self, user_id: str, key: str, default: Any | None = None) -> Any:
        with self.cursor() as cur:
            row = cur.execute("SELECT value FROM memory WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        if not row:
            return default
        return json.loads(row["value"])

    def save_trip(self, trip: Any) -> None:
        data = model_to_data(trip)
        now = datetime.now(timezone.utc).isoformat()
        trip_id = data["id"]
        user_id = data.get("user_id", "guest")
        title = data.get("title", "Untitled trip")
        destination = data.get("request", {}).get("destination") or data.get("itinerary", {}).get("destination")
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self.cursor() as cur:
            existing = cur.execute("SELECT created_at FROM trips WHERE id=?", (trip_id,)).fetchone()
            created_at = existing["created_at"] if existing else data.get("created_at", now)
            cur.execute(
                """
                INSERT INTO trips(id, user_id, title, destination, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    destination=excluded.destination,
                    data=excluded.data,
                    updated_at=excluded.updated_at
                """,
                (trip_id, user_id, title, destination, payload, created_at, now),
            )

    def get_trip(self, trip_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT data FROM trips WHERE id=?"
        params: tuple[Any, ...] = (trip_id,)
        if user_id:
            sql += " AND user_id=?"
            params = (trip_id, user_id)
        with self.cursor() as cur:
            row = cur.execute(sql, params).fetchone()
        return json.loads(row["data"]) if row else None

    def latest_trip(self, user_id: str) -> dict[str, Any] | None:
        with self.cursor() as cur:
            row = cur.execute(
                "SELECT data FROM trips WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return json.loads(row["data"]) if row else None

    def list_trips(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            rows = cur.execute(
                "SELECT id, title, destination, created_at, updated_at FROM trips WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_booking(self, booking: Any) -> None:
        data = model_to_data(booking)
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bookings(id, user_id, trip_id, status, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    data=excluded.data,
                    updated_at=excluded.updated_at
                """,
                (
                    data["id"],
                    data.get("user_id", "guest"),
                    data.get("trip_id"),
                    data.get("status", "pending"),
                    payload,
                    data.get("created_at", now),
                    now,
                ),
            )

    def get_booking(self, booking_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT data FROM bookings WHERE id=?"
        params: tuple[Any, ...] = (booking_id,)
        if user_id:
            sql += " AND user_id=?"
            params = (booking_id, user_id)
        with self.cursor() as cur:
            row = cur.execute(sql, params).fetchone()
        return json.loads(row["data"]) if row else None

    def save_notification(self, notification: Any) -> None:
        data = model_to_data(notification)
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications(id, user_id, trip_id, data, created_at, sent)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET data=excluded.data, sent=excluded.sent
                """,
                (
                    data["id"],
                    data.get("user_id", "guest"),
                    data.get("trip_id"),
                    payload,
                    data.get("created_at", datetime.now(timezone.utc).isoformat()),
                    int(bool(data.get("sent", False))),
                ),
            )


database = Database()
