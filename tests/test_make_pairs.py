from datetime import datetime
import logging
from operator import and_
from unittest import mock
from app import app, db
from models import Task, User, Pair, Group, GroupsAndUsersAssociation
from uuid import uuid4
from random import choice, randint
from time import sleep
from celery import Celery
from sqlalchemy.orm import sessionmaker
from unittest.mock import create_autospec, MagicMock, patch
from sqlalchemy import alias, func, select

import pytest
import tasks
import os


logger = logging.getLogger(__name__)

USERNAMES = [
    "suzannevazquez",
    "johnerickson",
    "michellemitchell",
    "victoriataylor",
    "richardho",
    "sarayoder",
]


@pytest.fixture
def users():
    user_objs = []
    with app.app_context():
        for username in USERNAMES:
            user = User(
                username=username, email=f"{username}_{uuid4().__str__()[:8]}@santa.io"
            )
            user.save_to_db(db)
            user_objs.append(user)

        user_ids = [user.id for user in user_objs]

        yield user_objs

        user_objs = [User.query.filter_by(id=user_id).first() for user_id in user_ids]
        for user in user_objs:
            user.delete_from_db(db)


@pytest.fixture
def group(users):
    with app.app_context():
        new_group = Group(name="bricks-and-clicks")
        new_group.save_to_db(db)
        for user in users:
            group_and_user_assoc = GroupsAndUsersAssociation(
                group=new_group, user=user, group_admin=choice((0, 1))
            )
            group_and_user_assoc.save_to_db(db)

        group_id = new_group.id

        yield new_group

        new_group = Group.query.filter_by(id=group_id).first()
        for user_assoc in new_group.users:
            user_assoc.delete_from_db(db)

        new_group.delete_from_db(db)


@pytest.fixture
def pairs(group):
    with app.app_context():
        celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))
        task_entry = Task(
            started_at=datetime.now(),
            name="create_pairs",
            payload={
                "group_id": group.id,
                "initiator_id": "",
            },
            status="starting",
        )

        task_entry.save_to_db(db)

        task = celery.send_task("pair.create_pairs", (group.id,))

        if task.status == "FAILURE":
            raise ValueError(f"Something went wrong {task.result}")

        while True:
            if task.status == "PENDING":
                sleep(5)
            else:
                break

        pairs = [*Pair.query.filter_by(group_id=group.id)]
        pair_ids = [pair.id for pair in pairs]

        yield pairs

        for pair_id in pair_ids:
            pair = Pair.query.filter_by(id=pair_id).first()
            pair.delete_from_db(db)


def test_all_members_have_been_paired(pairs):
    group = pairs[0].group
    assert len(pairs) == len(group.users)


def test_no_one_is_their_own_secret_santa(pairs):
    for pair in pairs:
        giver, receiver = pair.giver, pair.receiver
        assert giver != receiver


def test_no_one_received_their_santa_from_last_time(pairs):
    old_pairs = [(pair.giver, pair.receiver) for pair in pairs]
    old_pairs_with_usernames = [
        (pair.giver.username, pair.receiver.username) for pair in pairs
    ]

    group = pairs[0].group

    task = (
        Task.query.filter(
            and_(
                Task.name == "create_pairs",
                Task.payload["group_id"].as_integer() == group.id,
            )
        )
        .order_by(Task.finished_at.desc())
        .first()
    )
    task.status = "starting"

    db.session.add(task)
    db.session.flush()

    fake_weighted_set = []
    for i, pair in enumerate(old_pairs):
        x, y = pair
        fake_weighted_set.append((x, (2 * i) + 1))

    mocked_async_pair = MagicMock()

    def mocked_async_pair_side_effect(*args, **kwargs):
        if mocked_async_pair_side_effect.counter == 0:
            mocked_async_pair_side_effect.counter += 1
            return {
                "weighted_set": fake_weighted_set,
                "group_id": group.id,
            }
        else:
            mocked_async_pair_side_effect.counter += 1
            return {
                "weighted_set": [(u[0], randint(10, 100)) for u in old_pairs],
                "group_id": group.id,
            }

    mocked_async_pair_side_effect.counter = 0
    mocked_async_pair.side_effect = mocked_async_pair_side_effect
    tasks._make_pairs_async = mocked_async_pair
    tasks.make_pairs(group.id)

    givers = alias(User)
    receivers = alias(User)
    ranked_pairs = (
        select(
            Pair.id,
            Pair.giver_id,
            Pair.receiver_id,
            givers.c.username.label("giver_username"),
            receivers.c.username.label("receiver_username"),
            func.rank()
            .over(
                partition_by=Pair.group_id,
                order_by=Pair.timestamp.desc(),
            )
            .label("rank"),
        )
        .select_from(Pair)
        .join(receivers, receivers.c.id == Pair.receiver_id)
        .join(givers, givers.c.id == Pair.giver_id)
        .where(Pair.group_id == group.id)
        .cte()
    )

    latest_pairs_sql = (
        select(*(col for col in ranked_pairs.c if col.name != "rank"))
        .select_from(ranked_pairs)
        .where(ranked_pairs.c.rank == 1)
    )

    latest_pairs = db.session.execute(latest_pairs_sql).all()

    assert len(latest_pairs) == len(pairs)
    latest_pairs_with_usernames = []
    for pair in latest_pairs:
        _, x, y, x_name, y_name = pair
        assert (x, y) not in old_pairs
        latest_pairs_with_usernames.append((x_name, y_name))

    Pair.query.filter(Pair.id.in_(row[0] for row in latest_pairs)).delete()
