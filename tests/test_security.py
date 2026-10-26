import re

import pytest

from models import User


@pytest.fixture
def client(database):
    from app import app

    return app.test_client()


def admin_page_urls():
    """Every admin page that takes no URL arguments: the index and each model's list."""
    from app import app

    return sorted(
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/admin/") and "GET" in rule.methods and not rule.arguments
    )


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
        assert response.headers["Location"].startswith("/login"), url


def test_admin_pages_turn_away_non_admins(database, client):
    log_in_as(client, make_user(database, "notanadmin", password="password123"))

    for url in admin_page_urls():
        response = client.get(url)

        assert response.status_code == 302, url
        assert response.headers["Location"] == "/profile", url


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
