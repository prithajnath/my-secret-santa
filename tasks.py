import os
from celery import Celery
from time import time
from requests import get
from datetime import datetime
from models import Pair


class TaskRunner:
    def __init__(self, name, config):
        self.celery = Celery(name, broker=config.fetch("CELERY_BROKER_URL"))

    @self.celery.task
    def make_pairs(self, users, group):
        weighted_set = []
        for user in users:
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

        for index, giver in enumerate(pairs):
            receiver = pairs[(index + 1) % len(pairs)]
            new_pair = Pair(
                group=group, receiver=receiver, giver=giver, timestamp=datetime.now()
            )

            new_pair.save_to_db(db)
