from models import User, Participant
from getpass import getpass
from flask_script import Command
from app import db, send_email
from os import environ

class CreateSuperUser(Command):
    def run(self):
        username = input("Enter superuser user name : ")
        email = input("Enter superuser email : ")
        password = getpass("Enter superuser password : ")

        new_superuser = User(
            username=username,
            email=email,
            password=password,
            admin=True
        )

        new_superuser.save_to_db(db)
        print(f"superuser {username} : {email} created successfully")

class CreateProfiles(Command):
    def run(self):
        participants = Participant.query.all()
        users = [i.email for i in User.query.all()]
        for participant in participants:
            skip = input(f"Skip user {participant.email}? [y/n]\n")
            if skip == 'y':
                print("skipping...")
                continue
            elif skip == 'n':
                password = input(f"Enter password for {participant.email}\n")
                user = User.query.filter_by(email=participant.email).first()
                if not user:
                    user = User(
                        username=f"{participant.first_name.lower()}{participant.last_name.lower()}",
                        password=password,
                        email=participant.email,
                        participant=participant
                    )

                    user.save_to_db(db)
                    print(f"Created new user {user.username}")
                else:
                    user.set_password(password)
                    user.save_to_db(db)

                if environ.get("ENVIRONMENT") != "test":
                    sent = send_email(
                        'platts.sec@gmail.com',
                        'You got a password!!!',
                        [participant.email],
                        "password.html",
                        {
                            "first_name": participant.first_name,
                            "username": f"{participant.first_name.lower()}{participant.last_name.lower()}",
                            "password": password,
                            "url": f"{environ.get('PROTOCOL')}://{environ.get('HOSTNAME')}/login"
                        }
                    )

                    if sent:
                        print(f"Created new password for user {participant.email}!!")
                else:
                    print(f"Created new password for user {participant.email}!!")

            else:
                break
