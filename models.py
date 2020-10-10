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
    first_name = db.Column(db.String(20), unique=False, nullable=True)
    last_name = db.Column(db.String(20), unique=False, nullable=True)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    admin = db.Column(db.Boolean, unique=False, default=False)

    def __init__(self, username="test",
                 first_name="first_name",
                 last_name="last_name",
                 email="test@test.io",
                 password="test",
                 admin=False,
                 ):
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.admin = admin
        self.password = pbkdf2_sha256.hash(password)

    def verify_hash(self, password, hash):
        return pbkdf2_sha256.verify(password, hash)

    def set_password(self, password):
        self.password = pbkdf2_sha256.hash(password)

    def __str__(self):
        return self.email
