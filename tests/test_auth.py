from werkzeug.security import check_password_hash

from conftest import sign_in, submit


def test_registration_and_duplicate(app, client):
    data = {"name": "Ada Demo", "email": " ADA@EXAMPLE.TEST ", "password": "test-password",
            "confirm_password": "test-password"}
    assert submit(client, "/register", data).status_code == 303
    duplicate = submit(client, "/register", data)
    assert b"already exists" in duplicate.data
    user = app.extensions["repository"].user("ada@example.test")
    assert user["password_hash"] != data["password"]
    assert check_password_hash(user["password_hash"], data["password"])
    assert user["login_count"] == 0


def test_invalid_registration_and_csrf(client):
    assert client.post("/register").status_code == 400
    assert b"valid name and email" in submit(client, "/register", {"email": "bad"}).data
    data = {"name": "Ada Demo", "email": "ada@example.test", "password": "test-password",
            "confirm_password": "different-password"}
    assert b"same password" in submit(client, "/register", data).data


def test_login_count_credentials_and_logout(app, client):
    assert sign_in(client).location == "/home1"
    user = lambda: app.extensions["repository"].user("ada@example.test")
    assert user()["login_count"] == 1 and user()["last_login"]
    assert submit(client, "/logout", {}).status_code == 303
    assert client.get("/home1").location == "/login"
    bad = submit(client, "/login", {"email": "ada@example.test", "password": "wrong"})
    assert b"Incorrect email or password" in bad.data
    assert user()["login_count"] == 1
    assert sign_in(client).status_code == 303
    assert user()["login_count"] == 2
