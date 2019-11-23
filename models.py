from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from mixins import dbMixin
from flask_login import UserMixin
from uuid import uuid1

db = SQLAlchemy()


class User(dbMixin, UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    admin = db.Column(db.Boolean, unique=False, default=False)
    participant = db.relationship("Participant", backref="user", uselist=False)

    def __init__(self, username="test",
                 email="test@test.io",
                 password="test",
                 admin=False,
                 participant=None,
                 user_type_id=""):
        self.username = username
        self.email = email
        self.admin = admin
        self.password = pbkdf2_sha256.hash(password)
        self.participant = participant

    def verify_hash(self, password, hash):
        return pbkdf2_sha256.verify(password, hash)

    def set_password(self, password):
        self.password = pbkdf2_sha256.hash(password)

    def __str__(self):
        return self.email


class Participant(dbMixin, db.Model):
    __tablename__ = "participants"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(200), nullable=False)
    last_name = db.Column(db.String(200), nullable=False)
    hint = db.Column(db.String(500))
    address = db.Column(db.String(500))
    email = db.Column(db.String(200), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)

    def __init__(self, first_name="test",
                 last_name="test",
                 hint="test test",
                 address="test street",
                 email="test@test.io"):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.hint = hint
        self.address = address
