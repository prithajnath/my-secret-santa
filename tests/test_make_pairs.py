from datetime import datetime
import logging
from app import app, db
from models import Task, User, Pair, Group, GroupsAndUsersAssociation
from uuid import uuid4
from random import choice
from time import sleep
from celery import Celery
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, select

import pytest
import os


logger = logging.getLogger(__name__)


@pytest.fixture
def users():
    users = """
        leslieday
        christopherclark
        christinehartman
        davidbrown
        tracymcdaniel
        marcunderwood
        benjaminsolis
        allisonthomas
        stevendaniel
        kevinwheeler
        staceycarter
        veronicaanderson
        michaelriley
        jackjohnson
        rebeccajones
        melaniebradley
        gregorymendez
        alexcampbell
        shelleyfisher
        steveking
        kevingrant
        anajames
        matthewchavez
        nicholasgreene
        michaelthomas
        jefferybryant
        tinahudson
        julienguyen
        michaelcooper
        suzannevazquez
        johnerickson
        michellemitchell
        victoriataylor
        richardho
        sarayoder
    """.split()

    user_objs = []
    with app.app_context():
        for username in users:
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
