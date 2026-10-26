from flask import redirect, request
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


class AdminOnlyMixin:
    """Only logged-in admins may see or change anything in the admin panel."""

    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

    def inaccessible_callback(self, name, **kwargs):
        if current_user.is_authenticated:
            return redirect("/profile")
        else:
            return redirect(f"/login?next={request.path}")


class MyAdminIndexView(AdminOnlyMixin, AdminIndexView):
    pass


class AdminModelView(AdminOnlyMixin, ModelView):
    pass


def register(app, db):
    admin = Admin(app, index_view=MyAdminIndexView())
    admin.add_view(AdminModelView(User, db.session))
    admin.add_view(AdminModelView(GroupsAndUsersAssociation, db.session))
    admin.add_view(AdminModelView(Group, db.session))
    admin.add_view(AdminModelView(Pair, db.session))
    admin.add_view(AdminModelView(Task, db.session))
    admin.add_view(AdminModelView(EmailInvite, db.session))
    admin.add_view(AdminModelView(PasswordReset, db.session))
    admin.add_view(AdminModelView(GroupPairReveals, db.session))
    admin.add_view(AdminModelView(Message, db.session))
    admin.add_view(AdminModelView(UserOAuthProfile, db.session))
    admin.add_view(AdminModelView(Issue, db.session))
