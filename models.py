import json


from flask_sqlalchemy import SQLAlchemy, event
from passlib.hash import pbkdf2_sha256
from enum import Enum
from mixins import dbMixin
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid1, uuid4
from sql.materialized_views import AllAdminView, AllLatestPairsView

db = SQLAlchemy()


all_admin_materialized_view = AllAdminView(db)
all_latest_pairs_view = AllLatestPairsView(db)


class GroupsAndUsersAssociation(dbMixin, UserMixin, db.Model):
    __tablename__ = "groups_and_users"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), primary_key=True)
    group_admin = db.Column(db.Boolean, default=False)
    participating = db.Column(db.Boolean, default=True)
    group = db.relationship("Group", backref="_users")
    user = db.relationship("User", backref="_groups")

    def __str__(self):
        return f"{self.group} >--< #{self.user}"

    __repr__ = __str__


class User(dbMixin, UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(20), unique=False, nullable=True)
    last_name = db.Column(db.String(20), unique=False, nullable=True)
    hint = db.Column(db.String(2000), unique=False, nullable=True)
    address = db.Column(db.String(200), unique=False, nullable=True)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    admin = db.Column(db.Boolean, unique=False, default=False)
    groups = db.relationship("GroupsAndUsersAssociation", backref="_user")

    def __init__(
        self,
        username="test",
        first_name="first_name",
        last_name="last_name",
        email="test@test.io",
        password="test",
        hint="somehint",
        address="whereilive",
        admin=False,
    ):
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.admin = admin
        self.address = address
        self.hint = hint
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
    reveal_latest_pairs = db.Column(db.Boolean, default=False)
    users = db.relationship("GroupsAndUsersAssociation", backref="_group")

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def is_admin(self, user):
        admin_of = all_admin_materialized_view.query.filter_by(
            user_id=user.id, group_id=self.id
        )
        if admin_of.first():
            return True
        return False

    __repr__ = __str__


class GroupPairReveals(dbMixin, db.Model):
    __tablename__ = "group_pair_reveals"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))
    group = db.relationship("Group")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User")
    timestamp = db.Column(db.DateTime)

    def __str__(self):
        return f"{self.group.name} -> {self.timestamp}"

    __repr__ = __str__


class Pair(dbMixin, UserMixin, db.Model):
    __tablename__ = "pairs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    emailed = db.Column(db.Boolean, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))
    giver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    group = db.relationship("Group", backref="pairs")
    giver = db.relationship("User", foreign_keys=[giver_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class PairCreationStatus(dbMixin, db.Model):
    __tablename__ = "pair_creation_statuses"

    class Status(Enum):
        creating = 0
        finished = 1

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))
    group = db.relationship("Group")
    initiator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    initiator = db.relationship("User")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.Enum(Status))


class Task(dbMixin, db.Model):
    __tablename__ = "tasks"

    class TaskStatus(Enum):
        starting = 0
        processing = 1
        finished = 2

    id = db.Column(db.Integer, primary_key=True)
    payload = db.Column(db.JSON)
    error = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.Enum(TaskStatus))

    def __str__(self):
        return self.payload.fetch("name", "unnamed_task")


class EmailInvite(dbMixin, db.Model):
    # This is for email invites to people who haven't already signed up
    # We need to remember what group they were invited to
    # When they do sign up, we need to
    # 1. add them to that group
    # 2. redirect them to the my groups page
    # all from the sign up view, which means we need to check this table in that view
    # and drop the entry for this email after we have created an account for that email

    __tablename__ = "email_invites"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    invited_email = db.Column(db.String(120), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"))

    def __str__(self):
        return self.invited_email

    __repr__ = __str__


class PasswordReset(dbMixin, db.Model):
    __tablename__ = "password_resets"

    class ResetStatus(Enum):
        resetting = 0
        finished = 1

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = db.relationship("User")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.Enum(ResetStatus))


###########################################################
#              MATERIALIZED VIEWS                         #
###########################################################

# "before_insert" HOOKS


@event.listens_for(GroupsAndUsersAssociation, "before_insert", once=True)
def create_group_admin_materialized_view(mapper, connection, target):
    all_admin_materialized_view.create()


@event.listens_for(Pair, "before_insert", once=True)
def create_all_latest_pairs_view(mapper, connection, target):
    all_latest_pairs_view.create()


# "after_insert" HOOKS


@event.listens_for(GroupsAndUsersAssociation, "after_insert")
def refresh_group_admin_materialized_view(mapper, connection, target):
    all_admin_materialized_view.refresh()


@event.listens_for(Pair, "after_insert")
def refresh_all_latest_pairs_view(mapper, connection, target):
    all_latest_pairs_view.refresh()
