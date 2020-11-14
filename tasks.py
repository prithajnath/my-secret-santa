import os
import asyncio
from celery import Celery
from time import time
from requests import get
from datetime import datetime
from models import Pair, Group
from aiohttp import ClientSession
from app import db, app


celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

celery.conf.task_routes = {
    "pair.*": {"queue": "pairs_queue"},
    "email.*": {"queue": "emails_queue"},
}


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
                    user = user_association.user
                    tasks.append(add_weight_to_user(user, session))
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

    asyncio.run(make_pairs_async(group_id))

    return final_pairs
