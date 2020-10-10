from models import User 
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
