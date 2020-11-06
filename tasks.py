import os
from celery import Celery
from time import time
from requests import get
from datetime import datetime
from models import Pair, Group
from app import app, db


celery = Celery('tasks', broker=os.environ.get("CELERY_BROKER_URL"))


@celery.task()
def make_pairs(group_id):
    with app.app_context():
        group = Group.query.filter_by(id=group_id).first()
        weighted_set = []
        for user_association in group.users:
            user = user_association.user
            epoch = int(time())
            random_number = int(
                get(
                    f"https://qrng.anu.edu.au/wp-content/plugins/colours-plugin/get_one_binary.php?_={epoch}"
                ).content,
                2,
            )
            print(f"The quantuam random machine said {random_number}")
            weighted_set.append((user, random_number))

        pairs = [user for user, _ in sorted(weighted_set, key=lambda k: k[1])]

        pair_timestamp = datetime.now()
        final_pairs = []
        for index, giver in enumerate(pairs):
            receiver = pairs[(index + 1) % len(pairs)]
            new_pair = Pair(
                group=group, receiver=receiver, giver=giver, timestamp=pair_timestamp
            )

            new_pair.save_to_db(db)

            final_pairs.append((giver.username, receiver.username))

        return final_pairs
