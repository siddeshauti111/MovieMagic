import hmac
import logging
import os
import re
import secrets
from functools import wraps
from uuid import uuid4

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from config import settings
from services.booking_service import (CATALOG, CITIES, EMAIL, PAYMENTS, ROWS, SEATS,
                                      dates_for, make_booking, resolve, showtimes)
from services.database import BookingConflict, DuplicateEmail, SeatConflict, show_key, timestamp
from services.dynamodb_service import DynamoDatabase
from services.local_database import LocalDatabase
from services.notification_service import STATUS, Notifications


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_mapping(settings())
    if overrides:
        app.config.update(overrides)
    database = app.config.get("REPOSITORY")
    if database is None:
        database = (DynamoDatabase(app.config) if app.config["APP_MODE"] == "aws"
                    else LocalDatabase(app.config["DATABASE"]))
    notifications = app.config.get("NOTIFICATIONS") or Notifications(app.config)
    if app.config["APP_MODE"] == "local":
        app.logger.setLevel(logging.INFO)
    app.extensions["repository"] = database
    app.jinja_env.globals["notification_status"] = STATUS

    @app.before_request
    def prepare_request():
        g.user = session.get("user")
        if request.method == "POST":
            expected = session.get("csrf")
            supplied = request.form.get("csrf", "")
            if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                abort(400, "This form expired. Reload the page and try again.")

    @app.context_processor
    def template_helpers():
        return {"csrf_token": lambda: session.setdefault("csrf", secrets.token_urlsafe(32))}

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = ("default-src 'self'; object-src 'none'; "
                                                       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if g.get("user") or request.endpoint in {"login", "register", "logout"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    def require_login(view):
        @wraps(view)
        def guarded(*args, **kwargs):
            if not g.user:
                if request.endpoint == "seats_api":
                    return jsonify(error="Sign in to view seat availability."), 401
                flash("Sign in to continue.", "error")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return guarded

    @app.get("/")
    def index():
        return render_template("index.html", featured=CATALOG["titles"][:4])

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not 2 <= len(name) <= 100 or len(email) > 254 or not EMAIL.fullmatch(email):
                flash("Enter a valid name and email address.", "error")
            elif not 8 <= len(password) <= 128 or password != request.form.get("confirm_password"):
                flash("Use 8–128 characters and enter the same password twice.", "error")
            else:
                try:
                    database.register({"email": email, "id": str(uuid4()), "name": name,
                                       "password_hash": generate_password_hash(password),
                                       "login_count": 0, "created_at": timestamp(), "last_login": None})
                except DuplicateEmail:
                    flash("An account already exists for this email address.", "error")
                else:
                    flash("Account created. Sign in to book your first show.", "success")
                    return redirect(url_for("login"), 303)
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = database.user(email) if len(email) <= 254 and EMAIL.fullmatch(email) else None
            if user and len(password) <= 128 and check_password_hash(user["password_hash"], password):
                database.record_login(email)
                session.clear()
                session["user"] = {key: user[key] for key in ("id", "name", "email")}
                return redirect(url_for("home"), 303)
            flash("Incorrect email or password.", "error")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("index"), 303)

    def listing(template):
        city = request.args.get("location", session.get("city", "Pune"))
        if city not in CITIES:
            city = "Pune"
        session["city"] = city
        query = request.args.get("q", "").strip()[:100]
        genre = request.args.get("genre", "")
        movies = [movie for movie in CATALOG["titles"] if city in movie["cities"]
                  and query.casefold() in movie["title"].casefold()
                  and (not genre or movie["genre"] == genre)]
        return render_template(template, movies=movies, city=city, cities=CITIES, query=query,
                               genre=genre, genres=sorted({item["genre"] for item in CATALOG["titles"]}),
                               theaters=CITIES[city])

    @app.get("/home1")
    @require_login
    def home():
        return listing("home1.html")

    @app.get("/search")
    @require_login
    def search():
        return listing("search_results.html")

    @app.get("/booking")
    @require_login
    def booking():
        try:
            movie, theater = resolve(request.args.get("movie_id"), request.args.get("theater_id"))
        except ValueError as error:
            abort(404, str(error))
        return render_template("b1.html", movie=movie, theater=theater, rows=ROWS,
                               numbers=range(1, 11), dates=dates_for(movie), payments=PAYMENTS)

    @app.get("/api/seats")
    @require_login
    def seats_api():
        try:
            movie, theater = resolve(request.args.get("movie_id"), request.args.get("theater_id"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        date, time = request.args.get("show_date"), request.args.get("show_time")
        if date not in dates_for(movie):
            return jsonify(error="Choose a valid show date."), 400
        slots = showtimes(movie, theater, date)
        if time is None:
            time = slots[0] if slots else None
        elif time not in slots:
            return jsonify(error="Choose a valid future showtime."), 400
        booked = database.occupied(show_key(movie["id"], theater["id"], date, time), SEATS) if time else []
        return jsonify(booked=booked, showtimes=slots, show_time=time)

    @app.route("/tickets", methods=["GET", "POST"])
    @require_login
    def tickets():
        if request.method == "GET":
            last = session.get("last_ticket")
            return redirect(url_for("ticket", booking_id=last) if last else url_for("bookings"))
        form = request.form
        try:
            for _ in range(3):
                record, show = make_booking(form, g.user["id"])
                if record["email"] != g.user["email"]:
                    raise ValueError("Use the email address associated with your account.")
                try:
                    database.create_booking(record, show)
                    break
                except BookingConflict:
                    continue
            else:
                raise RuntimeError("Could not allocate a booking ID.")
        except (ValueError, SeatConflict) as error:
            flash("A selected seat was just booked. Please choose available seats."
                  if isinstance(error, SeatConflict) else str(error), "error")
            return redirect(url_for("booking", movie_id=form.get("movie_id"),
                                    theater_id=form.get("theater_id")), 303)
        session["last_ticket"] = record["booking_id"]
        try:
            status = notifications.send(record)
            database.set_notification(record["booking_id"], status)
            if status == "SIMULATED":
                app.logger.info("Simulated SNS confirmation for booking %s", record["booking_id"])
        except Exception as error:
            app.logger.warning("Notification step failed for %s (%s)",
                               record["booking_id"], type(error).__name__)
            flash("Booking confirmed. Email delivery could not be confirmed.", "error")
        return redirect(url_for("ticket", booking_id=record["booking_id"]), 303)

    @app.get("/ticket/<booking_id>")
    @require_login
    def ticket(booking_id):
        if not re.fullmatch(r"MVM-\d{8}-[0-9A-F]{8}", booking_id):
            abort(404)
        record = database.booking(booking_id)
        if not record or record["booked_by"] != g.user["id"]:
            abort(404)
        return render_template("tickets.html", ticket=record)

    @app.get("/bookings")
    @require_login
    def bookings():
        records = (item for item in database.history(g.user["id"])
                   if item["booking_status"] == "CONFIRMED")
        return render_template("bookings.html", bookings=sorted(records,
                               key=lambda item: item["created_at"], reverse=True))

    @app.get("/about")
    def about():
        return render_template("about.html")

    @app.get("/contact_us")
    def contact():
        return render_template("contact_us.html")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def request_error(error):
        return render_template("404.html", error=error), error.code

    @app.errorhandler(500)
    def server_error(error):
        if request.endpoint == "seats_api":
            return jsonify(error="Seat availability is temporarily unavailable."), 500
        return render_template("500.html"), 500

    return app


if __name__ == "__main__":
    create_app().run(port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
