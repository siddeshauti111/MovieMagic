import json
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from config import ROOT
from .database import show_key, timestamp

CATALOG = json.loads((ROOT / "data" / "movies.json").read_text(encoding="utf-8"))
TITLES = {title["id"]: title for title in CATALOG["titles"]}
CITIES = CATALOG["cities"]
THEATERS = {theater["id"]: dict(theater, city=city)
            for city, theaters in CITIES.items() for theater in theaters}
ROWS = "ABCDEFGH"
SEATS = [f"{row}{number}" for row in ROWS for number in range(1, 11)]
PAYMENTS = {"upi": "UPI (Demo)", "card": "Debit/Credit Card (Demo)", "counter": "Pay at Counter"}
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
IST = timezone(timedelta(hours=5, minutes=30))


def now():
    return datetime.now(IST)


def dates_for(movie):
    today = now().date()
    start = 2 if movie["kind"] == "event" else 0
    return [(today + timedelta(days=days)).isoformat() for days in range(start, 14)]


def showtimes(movie, theater, date):
    if date not in dates_for(movie):
        return []
    current = now()
    return [time for time in theater["times"]
            if date > current.date().isoformat() or time > current.strftime("%H:%M")]


def resolve(movie_id, theater_id):
    movie, theater = TITLES.get(movie_id), THEATERS.get(theater_id)
    if not movie or not theater or theater["city"] not in movie["cities"]:
        raise ValueError("Choose a valid title and theater.")
    return movie, theater


def make_booking(form, user_id):
    movie, theater = resolve(form.get("movie_id"), form.get("theater_id"))
    date, time = form.get("show_date"), form.get("show_time")
    if time not in showtimes(movie, theater, date):
        raise ValueError("Choose a valid future showtime.")
    seats = form.getlist("seats")
    if not seats or len(seats) != len(set(seats)) or any(seat not in SEATS for seat in seats):
        raise ValueError("Choose one or more distinct seats from the seat map.")
    name = form.get("customer_name", "").strip()
    email = form.get("email", "").strip().lower()
    phone = form.get("phone", "").strip()
    if not 2 <= len(name) <= 100 or len(email) > 254 or not EMAIL.fullmatch(email):
        raise ValueError("Enter a valid customer name and email address.")
    if not re.fullmatch(r"\+?[0-9][0-9 ()-]{7,18}", phone) or not 8 <= sum(c.isdigit() for c in phone) <= 15:
        raise ValueError("Enter a phone number with 8 to 15 digits.")
    method = form.get("payment_method")
    if method not in PAYMENTS:
        raise ValueError("Choose a payment method.")
    today = now().date()
    booking = {
        "booking_id": f"MVM-{today:%Y%m%d}-{uuid4().hex[:8].upper()}",
        "record_type": "BOOKING", "booked_by": user_id, "email": email,
        "customer_name": name, "phone": phone, "movie_id": movie["id"],
        "movie_name": movie["title"], "theater": theater["name"],
        "theater_id": theater["id"], "address": theater["address"], "location": theater["city"],
        "booking_date": today.isoformat(), "show_date": date, "show_time": time,
        "seats": sorted(seats, key=SEATS.index), "seat_count": len(seats),
        "ticket_price": theater["price"], "amount_paid": 0 if method == "counter" else theater["price"] * len(seats),
        "total_amount": theater["price"] * len(seats), "payment_method": PAYMENTS[method],
        "payment_status": "Due at counter" if method == "counter" else "Paid (simulated)",
        "booking_status": "CONFIRMED", "notification_status": "PENDING", "created_at": timestamp(),
    }
    return booking, show_key(movie["id"], theater["id"], date, time)
