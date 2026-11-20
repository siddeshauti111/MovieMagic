import pytest

from conftest import sign_in
from services.booking_service import CATALOG


@pytest.mark.parametrize("path", ["/", "/about", "/contact_us", "/register", "/login"])
def test_public_pages(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("path", ["/home1", "/booking", "/search", "/tickets", "/bookings", "/ticket/unknown"])
def test_protected_pages(client, path):
    assert client.get(path).location == "/login"


def test_search_by_name_city_and_genre(client):
    sign_in(client)
    assert b"Midnight Circuit" in client.get("/home1").data
    assert b"Upcoming events" in client.get("/home1").data
    found = client.get("/search?q=monsoon&location=Mumbai&genre=Drama")
    assert b"The Last Monsoon" in found.data and b"Midnight Circuit" not in found.data
    assert b"250" in found.data
    assert b"No shows found" in client.get("/search?q=monsoon&genre=Action").data
    assert b"No shows found" in client.get("/search?q=Salt&location=Bengaluru").data
    assert b"Salt &amp; Sea" in client.get("/search?q=Salt&location=Chennai").data


def test_bookable_catalog_and_assets(client):
    assert len([item for item in CATALOG["titles"] if item["kind"] == "movie"]) >= 12
    for item in CATALOG["titles"]:
        response = client.get("/static/" + item["poster"])
        assert response.status_code == 200, item["poster"]
        assert response.mimetype == "image/png"


def test_missing_and_invalid_booking(client):
    assert client.get("/missing").status_code == 404
    assert client.get("/api/seats").status_code == 401
    sign_in(client)
    assert client.get("/booking?movie_id=unknown").status_code == 404
    assert client.get("/api/seats?movie_id=unknown").status_code == 400
