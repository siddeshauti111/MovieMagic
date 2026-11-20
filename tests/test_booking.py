from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from conftest import sign_in, submit
from services.booking_service import now


def booking_data(**changes):
    return dict(movie_id="midnight-circuit", theater_id="pune-central",
                show_date=(now().date() + timedelta(days=1)).isoformat(),
                show_time="11:30", seats=["A1", "A10"], customer_name="Ada Demo",
                email="ada@example.test", phone="+91 9000000000", payment_method="upi", **changes)


def seats(client, data, **changes):
    params = {key: data[key] for key in ("movie_id", "theater_id", "show_date", "show_time")}
    return client.get("/api/seats", query_string=dict(params, **changes))


def test_booking_prg_trusted_price_and_ownership(app, client):
    sign_in(client)
    data = booking_data(ticket_price="1", amount_paid="1")
    page = client.get("/booking", query_string={"movie_id": data["movie_id"],
                                                 "theater_id": data["theater_id"]})
    assert page.data.count(b"data-seat=") == 80
    assert seats(client, data).json["booked"] == []
    response = submit(client, "/tickets", data)
    assert response.status_code == 303
    record = app.extensions["repository"].booking(response.location.split("/")[-1])
    assert record["ticket_price"] == 240 and record["amount_paid"] == 480
    assert record["notification_status"] == "SIMULATED"
    assert seats(client, data).json["booked"] == ["A1", "A10"]
    assert seats(client, data, show_time="15:15").json["booked"] == []
    ticket = client.get(response.location)
    assert b"Booking confirmed" in ticket.data and b"Paid (simulated)" in ticket.data
    assert b"Print ticket" in ticket.data
    assert record["booking_id"].encode() in client.get("/bookings").data
    assert client.get("/tickets").location == response.location
    other = app.test_client()
    sign_in(other, "other@example.test")
    assert other.get(response.location).status_code == 404
    assert b"no bookings yet" in other.get("/bookings").data


@pytest.mark.parametrize("changes", [
    {"seats": ["Z3"]}, {"seats": ["A1", "A1"]}, {"seats": []}, {"show_time": "02:00"},
    {"show_date": "2001-01-01"}, {"phone": "free"}, {"payment_method": "wire"},
    {"email": "someone@example.test"},
])
def test_invalid_booking(client, changes):
    sign_in(client)
    response = submit(client, "/tickets", dict(booking_data(), **changes))
    assert response.location.startswith("/booking?")
    assert b"no bookings yet" in client.get("/bookings").data


def test_multi_seat_rollback_and_counter_payment(app, client):
    sign_in(client)
    data = booking_data()
    assert submit(client, "/tickets", data).location.startswith("/ticket/")
    conflict = submit(client, "/tickets", dict(data, seats=["B3", "A10"]))
    assert conflict.location.startswith("/booking?")
    assert b"just booked" in client.get(conflict.location).data
    assert "B3" not in seats(client, data).json["booked"]
    counter = submit(client, "/tickets", dict(data, seats=["B3"], payment_method="counter"))
    record = app.extensions["repository"].booking(counter.location.split("/")[-1])
    assert record["payment_status"] == "Due at counter"
    assert record["amount_paid"] == 0 and record["total_amount"] == 240


def test_concurrent_bookings(app):
    barrier = Barrier(2)

    def reserve(email, seat):
        client = app.test_client()
        sign_in(client, email)
        barrier.wait(timeout=10)
        return submit(client, "/tickets", dict(booking_data(), email=email, seats=["D3", seat])).location

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(reserve, "a@example.test", "A3")
        b = pool.submit(reserve, "b@example.test", "B3")
        locations = [a.result(timeout=20), b.result(timeout=20)]
    assert sum(path.startswith("/ticket/") for path in locations) == 1
    client = app.test_client()
    sign_in(client, "a@example.test")
    assert seats(client, booking_data()).json["booked"] in (["A3", "D3"], ["B3", "D3"])
