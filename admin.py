from datetime import datetime

from flask import redirect, request, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import InputRequired

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
    db,
)

LOGIN_URL = "/admin/login/"


class AdminLoginForm(FlaskForm):
    username = StringField("Username", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])


def _safe_next(next_url):
    """Only follow `next` back into the admin panel, never to another site."""
    if next_url and next_url.startswith("/admin/") and not next_url.startswith("//"):
        return next_url
    return "/admin/"


class AdminOnlyMixin:
    """Only logged-in admins may see or change anything in the admin panel."""

    def is_accessible(self):
        return current_user.is_authenticated and current_user.admin

    def inaccessible_callback(self, name, **kwargs):
        return redirect(f"{LOGIN_URL}?next={request.path}")


class MyAdminIndexView(AdminOnlyMixin, AdminIndexView):
    # Reachable without being an admin, or nobody could log in
    PUBLIC_VIEWS = ("login", "logout")

    def _handle_view(self, name, **kwargs):
        if name in self.PUBLIC_VIEWS:
            return None
        return super()._handle_view(name, **kwargs)

    @expose("/login/", methods=["GET", "POST"])
    def login(self):
        next_url = _safe_next(request.args.get("next"))
        if current_user.is_authenticated and current_user.admin:
            return redirect(next_url)

        form = AdminLoginForm()
        error = None
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            # Same message whether the user is missing, not an admin or the password is
            # wrong, so the form doesn't reveal which accounts exist
            if user and user.admin and user.verify_hash(form.password.data, user.password):
                login_user(user)
                user.last_logged_in = datetime.now()
                user.save_to_db(db)
                return redirect(next_url)
            error = "Invalid username or password, or not an admin"

        return self.render("admin/login.html", form=form, error=error)

    @expose("/logout/", methods=["POST"])
    def logout(self):
        if current_user.is_authenticated:
            current_user.last_logged_out = datetime.now()
            current_user.save_to_db(db)
            logout_user()
        return redirect(url_for(".login"))


class AdminModelView(AdminOnlyMixin, ModelView):
    pass


def register(app):
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
