from datetime import datetime
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from models import Group, GroupsAndUsersAssociation, Pair, User, all_latest_pairs_view


@pytest.fixture
def client(database):
    from app import app

    return app.test_client()


def make_user(database, username):
    user = User(username=username, email=f"{username}@santa.io", password="password123")
    database.session.add(user)
    database.session.commit()
    return user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(identity=str(user.id))}"}


@pytest.fixture
def admin(database):
    return make_user(database, "anadmin")


@pytest.fixture
def member(database):
    return make_user(database, "amember")


@pytest.fixture
def group(database, admin, member):
    group = Group(name="Budget Santa")
    group.budget_cents = 2500
    database.session.add(group)
    database.session.add(GroupsAndUsersAssociation(user=admin, group=group, group_admin=True))
    database.session.add(GroupsAndUsersAssociation(user=member, group=group, group_admin=False))
    database.session.commit()
    return group


def create_group(client, user, **body):
    return client.post("/api/groups", json={"name": "New Santa", **body}, headers=auth(user))


def test_create_group_without_budget(client, admin):
    response = create_group(client, admin)

    assert response.status_code == 201
    assert response.get_json()["data"]["budget"] is None


def test_create_group_with_budget_defaults_to_usd(client, admin):
    response = create_group(client, admin, budget={"amount_cents": 3000})

    assert response.status_code == 201
    assert response.get_json()["data"]["budget"] == {"amount_cents": 3000, "currency": "USD"}


def test_create_group_with_other_currency(client, admin):
    response = create_group(client, admin, budget={"amount_cents": 150000, "currency": "INR"})

    assert response.get_json()["data"]["budget"] == {"amount_cents": 150000, "currency": "INR"}


@pytest.mark.parametrize(
    "budget",
    [
        {"amount_cents": -1},
        {"amount_cents": 1_000_001},
        {"amount_cents": 25.5},
        {"amount_cents": "2500"},
        {"amount_cents": True},
        {},
        {"amount_cents": 2500, "currency": "usd"},
        {"amount_cents": 2500, "currency": "BTC"},
        2500,
    ],
)
def test_create_group_rejects_bad_budget(client, admin, budget):
    response = create_group(client, admin, budget=budget)

    assert response.status_code == 400
    assert Group.query.filter_by(name="New Santa").first() is None


def test_admin_can_change_budget(client, admin, group):
    response = client.patch(
        f"/api/groups/{group.id}",
        json={"budget": {"amount_cents": 4000, "currency": "GBP"}},
        headers=auth(admin),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["budget"] == {"amount_cents": 4000, "currency": "GBP"}
    assert client.get(f"/api/groups/{group.id}", headers=auth(admin)).get_json()["data"][
        "budget"
    ] == {"amount_cents": 4000, "currency": "GBP"}


def test_admin_can_remove_budget(client, admin, group):
    response = client.patch(
        f"/api/groups/{group.id}", json={"budget": None}, headers=auth(admin)
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["budget"] is None


def test_member_cannot_change_budget(database, client, member, group):
    response = client.patch(
        f"/api/groups/{group.id}",
        json={"budget": {"amount_cents": 100}},
        headers=auth(member),
    )

    assert response.status_code == 403
    database.session.refresh(group)
    assert group.budget_cents == 2500


@pytest.mark.parametrize("body", [{}, {"name": "Renamed"}, {"budget": {"amount_cents": -5}}])
def test_update_group_rejects_bad_body(client, admin, group, body):
    response = client.patch(f"/api/groups/{group.id}", json=body, headers=auth(admin))

    assert response.status_code == 400


def test_update_missing_group(client, admin):
    response = client.patch("/api/groups/999", json={"budget": None}, headers=auth(admin))

    assert response.status_code == 404


def test_group_list_shows_budget(client, member, group):
    groups = client.get("/api/groups", headers=auth(member)).get_json()["data"]

    assert groups[0]["budget"] == {"amount_cents": 2500, "currency": "USD"}


def test_santa_shows_budget(database, client, admin, member, group):
    # The view keeps the latest draw, i.e. the pairs sharing the newest timestamp
    drawn_at = datetime.now()
    for giver, receiver in [(admin, member), (member, admin)]:
        database.session.add(
            Pair(
                channel_id=str(uuid4()),
                timestamp=drawn_at,
                group_id=group.id,
                giver_id=giver.id,
                receiver_id=receiver.id,
            )
        )
    database.session.commit()
    all_latest_pairs_view.refresh()

    data = client.get("/api/santa", headers=auth(admin)).get_json()["data"]

    budget = {"amount_cents": 2500, "currency": "USD"}
    assert data["santees"][0]["budget"] == budget
    assert data["santas"][0]["budget"] == budget
