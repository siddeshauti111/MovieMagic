import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .database import BookingConflict, DuplicateEmail, SeatConflict, lock_id, timestamp


class LocalDatabase:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY, data TEXT NOT NULL,
                    login_count INTEGER NOT NULL DEFAULT 0, last_login TEXT
                );
                CREATE TABLE IF NOT EXISTS bookings (
                    booking_id TEXT PRIMARY KEY, booked_by TEXT NOT NULL, data TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS bookings_owner ON bookings(booked_by);
                CREATE TABLE IF NOT EXISTS seat_locks (
                    lock_id TEXT PRIMARY KEY, booking_id TEXT NOT NULL REFERENCES bookings(booking_id)
                );
            """)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    def register(self, user):
        with self.connection() as db:
            try:
                db.execute("INSERT INTO users(email,data) VALUES (?,?)",
                           (user["email"], json.dumps(user)))
            except sqlite3.IntegrityError as error:
                raise DuplicateEmail from error

    def user(self, email):
        with self.connection() as db:
            row = db.execute("SELECT data,login_count,last_login FROM users WHERE email=?", (email,)).fetchone()
        if row:
            return dict(json.loads(row[0]), login_count=row[1], last_login=row[2])
        return None

    def record_login(self, email):
        with self.connection() as db:
            db.execute("UPDATE users SET login_count=login_count+1,last_login=? WHERE email=?",
                       (timestamp(), email))

    def occupied(self, show, seats):
        prefix = f"LOCK#{show}#"
        with self.connection() as db:
            rows = db.execute("SELECT lock_id FROM seat_locks WHERE lock_id LIKE ?", (prefix + "%",))
            booked = {key[len(prefix):] for (key,) in rows}
        return sorted(booked.intersection(seats))

    def create_booking(self, booking, show):
        with self.connection() as db:
            try:
                db.execute("INSERT INTO bookings VALUES (?,?,?)",
                           (booking["booking_id"], booking["booked_by"], json.dumps(booking)))
            except sqlite3.IntegrityError as error:
                raise BookingConflict from error
            try:
                db.executemany("INSERT INTO seat_locks VALUES (?,?)", [
                    (lock_id(show, seat), booking["booking_id"]) for seat in booking["seats"]
                ])
            except sqlite3.IntegrityError as error:
                raise SeatConflict from error

    def set_notification(self, booking_id, status):
        with self.connection() as db:
            db.execute("UPDATE bookings SET data=json_set(data,'$.notification_status',?) WHERE booking_id=?",
                       (status, booking_id))

    def booking(self, booking_id):
        with self.connection() as db:
            row = db.execute("SELECT data FROM bookings WHERE booking_id=?", (booking_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def history(self, user_id):
        with self.connection() as db:
            rows = db.execute("SELECT data FROM bookings WHERE booked_by=?", (user_id,))
            return [json.loads(row[0]) for row in rows]
