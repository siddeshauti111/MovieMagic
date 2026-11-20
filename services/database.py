import hashlib
from datetime import datetime, timezone


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def show_key(movie, theater, date, time):
    return hashlib.sha256(f"{movie}|{theater}|{date}|{time}".encode()).hexdigest()


def lock_id(show, seat):
    return f"LOCK#{show}#{seat}"


class DuplicateEmail(Exception):
    pass


class SeatConflict(Exception):
    pass


class BookingConflict(Exception):
    pass
