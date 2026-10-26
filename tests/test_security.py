import re

import pytest

from models import User


@pytest.fixture
def client(database):
    from app import app

    return app.test_client()


PUBLIC_ADMIN_PAGES = {"/admin/login/"}


def admin_page_urls():
    """Every admin-only page that takes no URL arguments, e.g. each model's list."""
    from app import app

    return sorted(
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/admin/")
        and "GET" in rule.methods
        and not rule.arguments
        and rule.rule not in PUBLIC_ADMIN_PAGES
    )


@pytest.fixture
def no_csrf():
    """Let form posts through without a CSRF token, for tests about other things."""
    from app import app

    app.config["WTF_CSRF_ENABLED"] = False
    yield
    app.config["WTF_CSRF_ENABLED"] = True


def log_in_as(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def make_user(database, username, password=None, admin=False):
    user = User(
        username=username,
        email=f"{username}@santa.io",
        password=password,
        admin=admin,
    )
    database.session.add(user)
    database.session.commit()
    return user


def test_admin_pages_cover_every_model():
    # Guards against the list below silently shrinking to just the index
    assert "/admin/user/" in admin_page_urls()
    assert "/admin/message/" in admin_page_urls()


def test_admin_pages_require_login(client):
    for url in admin_page_urls():
        response = client.get(url)

        assert response.status_code == 302, url
        assert response.headers["Location"] == f"/admin/login/?next={url}", url


def test_admin_pages_turn_away_non_admins(database, client):
    log_in_as(client, make_user(database, "notanadmin", password="password123"))

    for url in admin_page_urls():
        response = client.get(url)

        assert response.status_code == 302, url
        assert response.headers["Location"].startswith("/admin/login/"), url


def test_admin_pages_open_for_admins(database, client):
    log_in_as(client, make_user(database, "anadmin", password="password123", admin=True))

    # The index and each model's list; the other pages need a record id or query
    # parameters, and the two tests above cover who can reach them
    for url in admin_page_urls():
        if re.fullmatch(r"/admin/(\w+/)?", url):
            assert client.get(url).status_code == 200, url


def test_api_login_rejects_empty_password(database, client):
    make_user(database, "googleuser")

    response = client.post(
        "/api/auth/login", json={"username": "googleuser", "password": ""}
    )

    assert response.status_code == 400


@pytest.mark.parametrize("guess", ["test", "password", "googleuser"])
def test_user_created_without_password_cannot_log_in(database, client, guess):
    # How Google sign-in creates accounts
    make_user(database, "googleuser")

    response = client.post(
        "/api/auth/login", json={"username": "googleuser", "password": guess}
    )

    assert response.status_code == 401


def test_password_login_still_works(database, client):
    make_user(database, "realuser", password="password123")

    response = client.post(
        "/api/auth/login", json={"username": "realuser", "password": "password123"}
    )

    assert response.status_code == 200


def test_admin_login_page_is_public(client):
    assert client.get("/admin/login/").status_code == 200


def test_admin_can_log_in_and_out(database, client, no_csrf):
    make_user(database, "anadmin", password="password123", admin=True)

    response = client.post(
        "/admin/login/?next=/admin/user/",
        data={"username": "anadmin", "password": "password123"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/admin/user/"
    assert client.get("/admin/user/").status_code == 200

    assert client.post("/admin/logout/").status_code == 302
    assert client.get("/admin/user/").status_code == 302


@pytest.mark.parametrize(
    "username, password",
    [("anadmin", "wrongpassword"), ("notanadmin", "password123"), ("nobody", "x")],
)
def test_admin_login_refuses(database, client, no_csrf, username, password):
    make_user(database, "anadmin", password="password123", admin=True)
    make_user(database, "notanadmin", password="password123")

    response = client.post(
        "/admin/login/", data={"username": username, "password": password}
    )

    assert response.status_code == 200
    assert b"Invalid username or password, or not an admin" in response.data
    assert client.get("/admin/user/").status_code == 302


def test_admin_login_only_redirects_within_admin(database, client, no_csrf):
    make_user(database, "anadmin", password="password123", admin=True)

    response = client.post(
        "/admin/login/?next=https://evil.example/",
        data={"username": "anadmin", "password": "password123"},
    )

    assert response.headers["Location"] == "/admin/"


def test_admin_login_needs_csrf_token(database, client):
    make_user(database, "anadmin", password="password123", admin=True)

    client.post(
        "/admin/login/", data={"username": "anadmin", "password": "password123"}
    )

    assert client.get("/admin/user/").status_code == 302


def test_root_redirects_to_frontend(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://app.mysecretsanta.io"


@pytest.mark.parametrize(
    "url",
    [
        "/login",
        "/logout",
        "/register",
        "/signup",
        "/profile",
        "/groups",
        "/santa",
        "/invite",
        "/google_oauth",
        "/reset_password",
        "/group_message",
        "/reveal_secret_santa",
    ],
)
def test_old_pages_are_gone(client, url):
    response = client.get(url)

    assert response.status_code == 404
    assert response.get_json() == {"success": False, "error": {"message": "Not found"}}
