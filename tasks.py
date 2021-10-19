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
from typing import Tuple, Dict, Optional, Callable, Any, Union
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
from aiohttp.web import HTTPException, HTTPServerError
from aiohttp.client_exceptions import ClientConnectionError
from app import db, app, celery as app_celery


celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

celery.conf.task_routes = {
    "pair.*": {"queue": "pairs_queue"},
    "user.*": {"queue": "users_queue"},
}


def send_email(to: str, subject: str, template_name: str, payload: Dict):
    if os.getenv("ENV") == "production":
        domain_name = "www.mysecretsanta.io"
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain_name}/messages",
            auth=("api", os.getenv("MAILGUN_API_KEY")),
            data={
                "from": f"MySecretSanta <no-reply@{domain_name}>",
                "to": [to],
                "template": template_name,
                "h:X-Mailgun-Variables": json.dumps(payload),
                "subject": subject,
            },
        )

        print(response.status_code)
        print(response.content)
        print(response.headers)

    print(f"pretending to send and email to {to}")


# This is just a wrapper class for the retry decorator. Whenever we get an instance of this class it means something went wrong
# in the retry process
class RetryException:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

    __repr__ = __str__


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
                        return RetryException(
                            f"""
                        Caught an unknown exception. Refraining from retries
                        {e}
                        """
                        )
                    retries += 1
                    if retries == max_retries:
                        return RetryException(
                            f"""
                        Failed to execute {f.__name__} despite exponential backoff
                        {e}
                        """
                        )
                    else:
                        backoff_interval = 2 ** retries
                        jitter = uniform(1, 2)
                        total_backoff = backoff_interval + jitter
                        sys.stderr.write(
                            f"Retrying {f.__name__} #{retries}. Sleeping for {total_backoff}s"
                        )
                        sys.stderr.flush()
                        sleep(total_backoff)

        @wraps(f)
        async def _async_f_with_retries(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return await f(*args, **kwargs)
                except Exception as e:
                    # If we get an exception that we're not sure about, we simply catch it and log the error in the db
                    if type(e) not in exceptions:
                        return RetryException(
                            f"""
                        Caught an unknown exception. Refraining from retries
                        {e}
                        """
                        )
                    retries += 1
                    if retries == max_retries:
                        return RetryException(
                            f"""
                        Failed to execute {f.__name__} despite exponential backoff
                        {e}
                        """
                        )
                    else:
                        backoff_interval = 2 ** retries
                        jitter = uniform(1, 2)
                        total_backoff = backoff_interval + jitter
                        sys.stderr.write(
                            f"Retrying {f.__name__} #{retries}. Sleeping for {total_backoff}s"
                        )
                        sys.stderr.flush()
                        asyncio.sleep(total_backoff)

        if asyncio.iscoroutinefunction(f):
            return _async_f_with_retries
        else:
            return _f_with_retries

    return _retry


network_exception_retry = retry(
    exceptions=(
        HTTPError,
        ConnectionError,
        ClientConnectionError,
        Timeout,
        HTTPException,
        HTTPServerError,
    ),
    max_retries=5,
)


@network_exception_retry
async def _make_pairs_async(pipe={}):
    group_id = pipe["group_id"]
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
            print(f"Grabbing random number for {user}")
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

        return {**pipe, "weighted_set": weighted_set}


@network_exception_retry
def _make_pairs(pipe={}):
    weighted_set, group_id = pipe["weighted_set"], pipe["group_id"]
    with app.app_context():
        group = Group.query.filter_by(id=group_id).first()
        final_pairs = []
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

            final_pairs.append(giver.email)

            new_pair.save_to_db(db)

        return {**pipe, "final_pairs": final_pairs}


@network_exception_retry
def _send_secret_santa_email(giver_email, giver_first_name, group_id):
    with app.app_context():
        group = Group.query.filter_by(id=group_id).first()
        send_email(
            to=[giver_email],
            subject="You are someone's secret santa!!!",
            template_name="secret_santa",
            payload={
                "group_name": group.name,
                "santa_name": giver_first_name,
                "url": "https://app.mysecretsanta.io/login?next=/santa",
            },
        )


@network_exception_retry
def _invite_user_to_sign_up(to_email, admin_first_name, group_name):
    with app.app_context():
        send_email(
            to=[to_email],
            subject="You've been invited to a secret santa draw!!",
            template_name="secret_santa_invite",
            payload={"admin_first_name": admin_first_name, "group_name": group_name},
        )


@network_exception_retry
def _reset_user_password(email, user):
    with app.app_context():
        import random
        from os import getrandom

        random.seed(getrandom(100))
        _new_password = [
            chr(random.randint(50, 127)) for _ in range((random.randint(14, 20)))
        ]
        new_password = "".join(
            [i if i != " " else random.choice(";", "-", "_") for i in _new_password]
        )
        user.set_password(new_password)
        user.save_to_db(db)
        if os.getenv("ENV") == "production":
            send_email(
                to=[email],
                subject="Forgot your password?",
                template_name="password_reset",
                payload={"new_password": new_password},
            )

        else:
            # This is just to simulate network errors in a dev environemnt
            requests.get("https://www.mysecretsanta.io/math")
            print(new_password)


@celery.task(name="user.send_secret_santa_email")
def send_secret_santa_email(email, group_id):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        task = (
            Task.query.filter(
                and_(
                    Task.payload["email"].as_string() == email,
                    Task.name == "send_secret_santa_email",
                    Task.status == "starting",
                )
            )
            .order_by(Task.started_at.desc())
            .first()
        )

        task.status = "processing"
        task.save_to_db(db)

        result = _send_secret_santa_email(user.email, user.first_name, group_id)

        task.status = "finished"
        task.error = str(result)
        task.finished_at = datetime.now()
        task.save_to_db(db)


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
        task.error = str(result)
        task.finished_at = datetime.now()
        task.save_to_db(db)


@celery.task(name="user.invite_user_to_sign_up")
def invite_user_to_sign_up(to_email, admin_first_name, group_name):
    with app.app_context():
        task = (
            Task.query.filter(
                and_(
                    Task.payload["to_email"].as_string() == to_email,
                    Task.payload["admin_first_name"].as_string() == admin_first_name,
                    Task.payload["group_name"].as_string() == group_name,
                    Task.name == "invite_user_to_sign_up",
                    Task.status == "starting",
                )
            )
            .order_by(Task.started_at.desc())
            .first()
        )

        task.status = "processing"
        task.save_to_db(db)

        result = _invite_user_to_sign_up(to_email, admin_first_name, group_name)

        task.status = "finished"
        task.error = str(result)
        task.finished_at = datetime.now()
        task.save_to_db(db)


def chain(*args, pipe={}):
    for func in args:
        if asyncio.iscoroutinefunction(func):
            result = asyncio.run(func(pipe=pipe))
        else:
            result = func(pipe=pipe)

        if type(result) == RetryException:
            return result

        pipe = {**pipe, **result}
    return result


@celery.task(name="pair.create_pairs")
def make_pairs(group_id):
    with app.app_context():
        task = Task.query.filter(
            and_(
                Task.status == "starting",
                Task.payload["group_id"].as_integer() == group_id,
            )
        ).first()

        task.status = "processing"
        task.save_to_db(db)

        result = chain(_make_pairs_async, _make_pairs, pipe={"group_id": group_id})

        # result = asyncio.run(_make_pairs_async(pipe={"group_id": group_id}))

        task.status = "finished"
        task.finished_at = datetime.now()
        task.save_to_db(db)

        # Update pair creation status
        if type(result) == RetryException:
            task.error = str(result)
            task.save_to_db(db)
        else:
            final_pairs = result["final_pairs"]
            # Refresh materialzed view manually just to be safe
            all_latest_pairs_view.refresh()

            for giver in final_pairs:
                send_email_task = Task(
                    name="send_secret_santa_email",
                    payload={"email": giver, "group_id": group_id},
                    started_at=datetime.now(),
                    status="starting",
                )

                send_email_task.save_to_db(db)

                app_celery.send_task("user.send_secret_santa_email", (giver, group_id))
