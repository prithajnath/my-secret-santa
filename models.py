from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from mixins import dbMixin

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __init__(self, username="test",
                 email="test@test.io",
                 password="test",
                 user_type_id=""):
        self.username = username
        self.email = email
        self.password = pbkdf2_sha256.hash(password)

class Participant(db.Model):
    __tablename__ = "participants"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(20), nullable=False)
    last_name = db.Column(db.String(20), nullable=False)
    hint = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __init__(self, first_name="test",
                 last_name="test",
                 email="test@test.io"):
        self.first_name = first_name
        self.last_name = lasst_name
        self.email = email
