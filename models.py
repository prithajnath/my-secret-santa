from flask_sqlalchemy import SQLAlchemy
from passlib.hash import pbkdf2_sha256
from mixins import dbMixin
from flask_login import UserMixin
from uuid import uuid1

db = SQLAlchemy()

class GroupsAndUsersAssociation(dbMixin, UserMixin, db.Model):
    __tablename__ = 'groups_and_users'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)
    group_admin = db.Column(db.Boolean, default=False)
    group = db.relationship("Group", backref="_users")
    user = db.relationship("User", backref="_groups")

    def __str__(self):
        return f"{self.group} >--< #{self.user}"

    __repr__ = __str__

class User(dbMixin, UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    first_name = db.Column(db.String(20), unique=False, nullable=True)
    last_name = db.Column(db.String(20), unique=False, nullable=True)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    admin = db.Column(db.Boolean, unique=False, default=False)
    groups = db.relationship('GroupsAndUsersAssociation', backref='_user')

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
    

    __repr__ = __str__


class Group(dbMixin, UserMixin, db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    users = db.relationship('GroupsAndUsersAssociation', backref='_group')

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    __repr__ = __str__

class Pair(dbMixin, UserMixin, db.Model):
    __tablename__ = "pairs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Date)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    giver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    group = db.relationship('Group', backref='pairs')
    giver = db.relationship('User', foreign_keys=[giver_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
