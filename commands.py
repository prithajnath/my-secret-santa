from models import User, Group, GroupsAndUsersAssociation
from getpass import getpass
from flask_script import Command
from faker import Faker
from app import db, send_email
from os import environ
from random import choice, choices
from uuid import uuid4


class CreateSuperUser(Command):
    def run(self):
        username = input("Enter superuser user name : ")
        email = input("Enter superuser email : ")
        password = getpass("Enter superuser password : ")

        new_superuser = User(
            username=username, email=email, password=password, admin=True
        )

        new_superuser.save_to_db(db)
        print(f"superuser {username} : {email} created successfully")


class SeedDatabase(Command):
    def run(self):
        if environ.get("ENV") != "production":
            fake = Faker()

            users = [(fake.first_name(), fake.last_name()) for _ in range(1000)]
            user_objects = []
            for first_name, last_name in users:
                username = f"{first_name}{last_name}".lower()[:20]
                email = f"{username}_{uuid4().__str__()[:8]}@santa.io"
                print(f"adding {username}")
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

        else:
            print("Can't run this command in production")
