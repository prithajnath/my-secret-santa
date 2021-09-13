import os
import sendgrid
import json
import sys
import requests
import asyncio
from celery import Celery
from time import time
from requests import get
from functools import wraps
from typing import Tuple
from random import uniform
from time import sleep
from sqlalchemy.types import Unicode
from sqlalchemy import and_
from requests.exceptions import HTTPError, ConnectionError, Timeout
from datetime import datetime
from models import (
    Pair,
    Group,
    User,
    Task,
    PasswordReset,
    all_latest_pairs_view,
    PairCreationStatus,
)
from aiohttp import ClientSession
from python_http_client.exceptions import HTTPError
from app import db, app


celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

celery.conf.task_routes = {
    "pair.*": {"queue": "pairs_queue"},
    "user.*": {"queue": "users_queue"},
}


def retry(exceptions: Tuple, max_retries: int = 3):
    """
    Create retry decorators by passing a list/tuple of exceptions. Can also set max number of retries
    Implements exponential backoff with random jitter
    Usage:
        arithmetic_exception_retry = retry(exceptions=(FloatingPointError, OverflowError, ZeroDivisionError), max_retries=2)

        @arithmetic_exception_retry
        def _calculate_center_of_gravity(mass):
            ...
    """

    def _retry(f):
        @wraps(f)
        def _f_with_retries(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    # If we get an exception that we're not sure about, we simply catch it and log the error in the db
                    if type(e) not in exceptions:
                        return f"""
                        Caught an unknown exception. Refraining from retries
                        {e}
                        """
                    retries += 1
                    if retries == max_retries:
                        return f"""
                        Failed to execute {f.__name__} despite exponential backoff
                        {e}
                        """
                    else:
                        backoff_interval = 2 ** retries
                        jitter = uniform(1, 2)
                        total_backoff = backoff_interval + jitter
                        sys.stderr.write(
                            f"Retrying {f.__name__} #{retries}. Sleeping for {total_backoff}s"
                        )
                        sys.stderr.flush()
                        sleep(total_backoff)

        return _f_with_retries

    return _retry


network_exception_retry = retry(
    exceptions=(HTTPError, ConnectionError, Timeout), max_retries=5
)


@network_exception_retry
def _reset_user_password(email, user):
    with app.app_context():
        import random
        from os import getrandom

        random.seed(getrandom(100))
        new_password = "".join(
            [chr(random.randint(50, 127)) for _ in range((random.randint(14, 20)))]
        )
        user.set_password(new_password)
        user.save_to_db(db)
        if os.getenv("ENV") == "production":
            domain_name = "www.mysecretsanta.io"
            response = requests.post(
                f"https://api.mailgun.net/v3/{domain_name}/messages",
                auth=("api", os.getenv("MAILGUN_API_KEY")),
                data={
                    "from": f"Prithaj <prithaj@{domain_name}>",
                    "to": [email],
                    "template": "password_reset",
                    "h:X-Mailgun-Variables": json.dumps({"new_password": new_password}),
                    "subject": "Forgot your password?",
                },
            )

            print(response.status_code)
            print(response.content)
            print(response.headers)
        else:
            print(new_password)


@celery.task(name="user.reset_password")
def reset_user_password(email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        task = (
            Task.query.filter(
                and_(
                    Task.payload["email"].as_string() == email,
                    Task.name == "reset_user_password",
                    Task.status == "starting",
                )
            )
            .order_by(Task.started_at.desc())
            .first()
        )

        task.status = "processing"
        task.save_to_db(db)

        result = _reset_user_password(email, user)

        task.status = "finished"
        task.error = result
        task.finished_at = datetime.now()
        task.save_to_db(db)


@celery.task(name="user.invite")
def invite_user_to_sign_up(to_email, admin_first_name, group_name):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    template_id = os.environ.get("SENDGRID_INVITE_TEMPLATE_ID")
    data = {
        "from": {"email": "prithaj.nath@theangrydev.io"},
        "personalizations": [
            {
                "to": [{"email": to_email}],
                "subject": "SECRET SANTAAA!!!!!",
                "dynamic_template_data": {
                    "admin_first_name": admin_first_name,
                    "group_name": group_name,
                },
            }
        ],
        "template_id": template_id,
    }

    response = None
    try:
        response = sg.client.mail.send.post(request_body=data)
    except HTTPError as e:
        print(e.to_dict)
    if response:
        print(response.status_code)
        print(response.body)
        print(response.headers)


@celery.task(name="pair.create")
def make_pairs(group_id):
    final_pairs = []

    async def make_pairs_async(group_id):
        with app.app_context():
            group = Group.query.filter_by(id=group_id).first()
            weighted_set = []

            async def grab_random_number_for_user(session):
                import json

                epoch = int(time())
                url = f"https://qrng.anu.edu.au/wp-content/plugins/colours-plugin/get_one_binary.php?_={epoch}"
                resp = await session.request(method="GET", url=url)
                resp.raise_for_status()
                number = int(await resp.text(), 2)
                return number

            async def add_weight_to_user(user, session):
                random_number = await grab_random_number_for_user(session)
                print(f"The quantuam random machine said {random_number}")
                weighted_set.append((user, random_number))

            async with ClientSession() as session:
                tasks = []
                for user_association in group.users:
                    if user_association.participating:
                        user = user_association.user
                        tasks.append(add_weight_to_user(user, session))
                    else:
                        print(
                            f"Skipping user {user_association.user} because they chose not to participate"
                        )
                await asyncio.gather(*tasks)

            pairs = [user for user, _ in sorted(weighted_set, key=lambda k: k[1])]

            pair_timestamp = datetime.now()
            for index, giver in enumerate(pairs):
                receiver = pairs[(index + 1) % len(pairs)]
                new_pair = Pair(
                    group=group,
                    receiver=receiver,
                    giver=giver,
                    timestamp=pair_timestamp,
                )

                final_pairs.append((giver.username, receiver.username))

                new_pair.save_to_db(db)

                if os.getenv("ENV") == "production":
                    sg = sendgrid.SendGridAPIClient(
                        api_key=os.environ.get("SENDGRID_API_KEY")
                    )
                    template_id = os.environ.get("SENDGRID_PAIR_TEMPLATE_ID")
                    data = {
                        "from": {"email": "prithaj.nath@theangrydev.io"},
                        "personalizations": [
                            {
                                "to": [{"email": giver.email}],
                                "subject": "YOU ARE SOMEONE'S SECRET SANTAAA!!!!!",
                                "dynamic_template_data": {
                                    "giver": giver.first_name,
                                    "receiver": f"{receiver.first_name} {receiver.last_name}",
                                    "receiver_address": receiver.address,
                                    "receiver_interests": receiver.hint,
                                },
                            }
                        ],
                        "template_id": template_id,
                    }

                    response = None
                    try:
                        response = sg.client.mail.send.post(request_body=data)
                    except HTTPError as e:
                        print(e.to_dict)
                    if response:
                        print(response.status_code)
                        print(response.body)
                        print(response.headers)

                new_pair.emailed = True
                new_pair.save_to_db(db)

            # Refresh materialzed view manually just to be safe
            all_latest_pairs_view.refresh()

            # Update pair creation status
            status = PairCreationStatus.query.filter_by(
                group_id=group_id, status="creating"
            ).first()
            status.status = "finished"
            status.finished_at = datetime.now()
            status.save_to_db(db)

    asyncio.run(make_pairs_async(group_id))

    return final_pairs
