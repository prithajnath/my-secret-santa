from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from models import User, Group, GroupsAndUsersAssociation, Pair, EmailInvite
from flask_login import current_user
from flask import redirect


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
    admin.add_view(ModelView(EmailInvite, db.session))
