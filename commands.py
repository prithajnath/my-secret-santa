import click
from getpass import getpass
from faker import Faker
from os import environ
from random import choice, choices
from uuid import uuid4
from datetime import datetime


def register_commands(app, db):
    """Register CLI commands with the Flask app."""
    from models import User, Group, GroupsAndUsersAssociation, Message, Pair

    @app.cli.command("createsuperuser")
    def create_superuser():
        """Create a new superuser."""
        username = input("Enter superuser user name : ")
        email = input("Enter superuser email : ")
        password = getpass("Enter superuser password : ")

        new_superuser = User(
            username=username, email=email, password=password, admin=True
        )

        new_superuser.save_to_db(db)
        click.echo(f"superuser {username} : {email} created successfully")

    @app.cli.command("geocode-addresses")
    @click.option("--group-id", type=int, help="Only geocode members of this group")
    @click.option("--dry-run", is_flag=True, help="Report matches without saving")
    @click.option(
        "--retry-unmatched", is_flag=True, help="Also retry addresses marked unmatched"
    )
    def geocode_addresses(group_id, dry_run, retry_unmatched):
        """Geocode free-text user addresses with the US Census geocoder."""
        import time

        import requests
        from sqlalchemy import func, or_

        statuses = ["pending", "unmatched"] if retry_unmatched else ["pending"]
        query = User.query.filter(
            User.address.isnot(None),
            func.btrim(User.address) != "",
            or_(User.geocode_status.in_(statuses), User.geocode_status.is_(None)),
        )
        if group_id:
            query = query.join(
                GroupsAndUsersAssociation,
                GroupsAndUsersAssociation.user_id == User.id,
            ).filter(GroupsAndUsersAssociation.group_id == group_id)
        users = query.order_by(User.id).all()

        click.echo(
            f"{len(users)} address(es) to geocode{' (dry run)' if dry_run else ''}"
        )
        matched = unmatched = failed = 0
        for user in users:
            try:
                response = requests.get(
                    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
                    params={
                        "address": user.address,
                        "benchmark": "Public_AR_Current",
                        "format": "json",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                matches = response.json()["result"]["addressMatches"]
            except (requests.RequestException, KeyError, ValueError) as e:
                failed += 1
                click.echo(f"  {user.username}: lookup failed ({e.__class__.__name__}), left pending")
                continue

            if not matches:
                unmatched += 1
                click.echo(f"  {user.username}: no match")
                if not dry_run:
                    user.geocode_status = "unmatched"
                    user.save_to_db(db)
                continue

            match = matches[0]
            components = match["addressComponents"]
            city = components["city"].title()
            click.echo(f"  {user.username}: matched {city}, {components['state']}")
            matched += 1
            if not dry_run:
                # Keep the user's own address text (Census drops apartment/unit numbers)
                # and only fill in what the map and santa labels need
                user.location = (
                    f"SRID=4326;POINT({match['coordinates']['x']} {match['coordinates']['y']})"
                )
                user.city = city
                user.state = components["state"]
                user.zip = components["zip"]
                user.geocode_status = "census"
                user.geocoded_at = datetime.now()
                user.save_to_db(db)

            # Be polite to the free Census API
            time.sleep(0.2)

        click.echo(f"matched {matched}, unmatched {unmatched}, failed {failed}")

    @app.cli.command("seed")
    def seed_database():
        """Seed the database with fake data (non-production only)."""
        if environ.get("ENV") != "production":
            fake = Faker()

            users = [(fake.first_name(), fake.last_name()) for _ in range(1000)]
            user_objects = []
            for first_name, last_name in users:
                username = f"{first_name}{last_name[0]}{uuid4().__str__()[:8]}".lower()[
                    :20
                ]
                email = f"{username}_{uuid4().__str__()[:8]}@santa.io"
                click.echo(f"adding {username}")
                random_user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password="helloworld",
                    address=fake.address(),
                    hint=" ".join(fake.words(50)),
                )

                random_user.save_to_db(db)
                user_objects.append(random_user)

            distinct = set()
            for _ in range(50):
                members = choices(user_objects, k=10)
                group_name = fake.bs()
                group = Group(name=group_name)
                group.save_to_db(db)
                for member in members:
                    if (member.id, group.id) not in distinct:
                        group_assoc = GroupsAndUsersAssociation(
                            user=member, group=group, group_admin=bool(choice((0, 1)))
                        )
                        group_assoc.save_to_db(db)
                        distinct.add((member.id, group.id))

                dt = datetime.now()
                for i in range(len(members)):
                    user1, user2 = members[i], members[(i + 1) % len(members)]
                    click.echo(f"Pairing {user1} and {user2}")

                    pair_channel_id = str(uuid4())
                    pair = Pair(
                        channel_id=pair_channel_id,
                        timestamp=dt,
                        group_id=group.id,
                        giver_id=user1.id,
                        receiver_id=user2.id,
                    )

                    pair.save_to_db(db)
                    click.echo(f"Adding messages for {user1} and {user2}")
                    # create some back and forth (10 messages)
                    for j in range(10):
                        if j % 2 == 0:
                            # user1 sends a message to user2
                            message = Message(
                                pair_channel_id=pair_channel_id,
                                sender_id=user1.id,
                                receiver_id=user2.id,
                                text=fake.words(choice((5, 10, 20))),
                            )
                        else:
                            # user2 sends a message to user1
                            message = Message(
                                pair_channel_id=pair_channel_id,
                                sender_id=user2.id,
                                receiver_id=user1.id,
                                text=fake.words(choice((5, 10, 20))),
                            )
                        message.save_to_db(db)

        else:
            click.echo("Can't run this command in production")
