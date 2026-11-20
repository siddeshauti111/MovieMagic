import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "APP_MODE": "local", "SECRET_KEY": "test-only",
                       "SESSION_COOKIE_SECURE": False, "DATABASE": tmp_path / "movie.sqlite3"})


@pytest.fixture
def client(app):
    return app.test_client()


def submit(client, path, data):
    with client.session_transaction() as session:
        token = session.get("csrf", "test-csrf")
        session["csrf"] = token
    return client.post(path, data=dict(data, csrf=token))


def sign_in(client, email="ada@example.test"):
    submit(client, "/register", {"name": "Ada Demo", "email": email,
                                 "password": "test-password", "confirm_password": "test-password"})
    return submit(client, "/login", {"email": email, "password": "test-password"})
