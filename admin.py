from flask import redirect
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from models import (
    EmailInvite,
    Group,
    GroupPairReveals,
    GroupsAndUsersAssociation,
    Issue,
    Message,
    Pair,
    PasswordReset,
    Task,
    User,
    UserOAuthProfile,
)


class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

    def inaccessible_callback(self, name, *kwargs):
        if current_user.is_authenticated:
            return redirect("/profile")
        else:
            return redirect("/login")


def register(app, db):
    admin = Admin(app, index_view=MyAdminIndexView())
    admin.add_view(ModelView(User, db.session))
    admin.add_view(ModelView(GroupsAndUsersAssociation, db.session))
    admin.add_view(ModelView(Group, db.session))
    admin.add_view(ModelView(Pair, db.session))
    admin.add_view(ModelView(Task, db.session))
    admin.add_view(ModelView(EmailInvite, db.session))
    admin.add_view(ModelView(PasswordReset, db.session))
    admin.add_view(ModelView(GroupPairReveals, db.session))
    admin.add_view(ModelView(Message, db.session))
    admin.add_view(ModelView(UserOAuthProfile, db.session))
    admin.add_view(ModelView(Issue, db.session))
