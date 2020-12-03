from flask import Flask, render_template, request, redirect, jsonify
from datetime import datetime
from models import db, Group, User, GroupsAndUsersAssociation, EmailInvite
from serializers import ma
from celery import Celery
from flask_mail import Mail, Message
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_bootstrap import Bootstrap
from forms import (
    SignUpForm,
    LoginForm,
    PairForm,
    ProfileEditForm,
    InviteUserToGroupForm,
    CreateGroupForm,
    ChangePasswordForm,
    CreatePairsForm,
    LeaveGroupForm
)
from random import choice
from kombu.serialization import register
from serializers import UserSchema, GroupSchema

import os
import admin
from datetime import datetime
import requests as r
import json
import maya

GIPHY_API_KEY = os.environ.get("GIPHY_API_KEY")


app = Flask(__name__)
app.config.update(
    dict(
        DEBUG=False if os.environ.get("ENV") == "production" else True,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USE_SSL=False,
        MAIL_USERNAME=f"{os.environ.get('MAIL_USERNAME')}@gmail.com",
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=True,
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        CSRF_ENABLED=True,
    )
)

Bootstrap(app)
db.init_app(app)
ma.init_app(app)
mail = Mail(app)
admin.register(app, db)
login_manager = LoginManager()
login_manager.init_app(app)


celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def send_email(sender, subject, recipients, template, data):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.html = render_template(template, data=data)

    sent = True
    with app.app_context():
        try:
            mail.send(msg)
        except:
            sent = False
    return sent


# Routes
@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.verify_hash(form.current_password.data, current_user.password):
            current_user.set_password(form.new_password.data)
            current_user.save_to_db(db)

            return redirect("/profile")
    return render_template("change_password.html", form=form)


@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileEditForm()
    if form.validate_on_submit():
        hint = form.hint.data
        address = form.address.data
        current_user.hint = hint
        current_user.address = address

        current_user.save_to_db(db)

        return redirect("/profile")
    hint = current_user.hint
    address = current_user.address
    return render_template("edit_profile.html", form=form, hint=hint, address=address)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def participants_profile():
    return render_template("profile.html")


@app.route("/santa", methods=["GET", "POST"])
@login_required
def santa():
    form = PairForm()
    if request.method == "POST":
        group_id = request.args.get("group_id")
        task = celery.send_task("pair.create", (group_id,))

        if task.status == "PENDING":
            message = "Pairs are being created. Should be done soon"
            return render_template(
                "santa.html", group_id=group_id, form=form, message=message
            )

    return render_template("santa.html", form=form)


@app.route("/groups", methods=["GET", "POST"])
@login_required
def group():
    create_group_form = CreateGroupForm()
    invite_user_to_group_form = InviteUserToGroupForm()
    create_pairs_form = CreatePairsForm()
    if request.method == "POST":
        if create_group_form.validate_on_submit():
            new_group = Group(name=create_group_form.name.data)
            new_group.save_to_db(db)
            new_group_assoc = GroupsAndUsersAssociation(group=new_group, user=current_user, group_admin=True)
            new_group_assoc.save_to_db(db)

            db.session.commit()
            return render_template("group.html",
                group=new_group,
                create_pairs_form=create_pairs_form,
                form=invite_user_to_group_form
            )

        if create_pairs_form.validate_on_submit():
            group_id = request.args.get("group_id")
            print(f"Creating pairs for {group_id}")
            group = Group.query.filter_by(id=group_id).first()

            if group.is_admin(current_user) and current_user.is_authenticated:
                task = celery.send_task("pair.create", (group_id,))

                if task.status == "PENDING":
                    timestamp = maya.MayaDT.from_datetime(datetime.utcnow())
                    message = f"Pair creation has been initiated at {timestamp.__str__()}. Sit tight!"
                    return render_template("group.html",
                        message=message,
                        group=group,
                        form=invite_user_to_group_form,
                        create_pairs_form=create_pairs_form
                    )

        
        if invite_user_to_group_form.validate_on_submit():
            group_id = request.args.get("group_id")
            group = Group.query.filter_by(id=group_id).first()
            user = User.query.filter_by(email=invite_user_to_group_form.email.data).first()
            if user:
                new_group_assoc = GroupsAndUsersAssociation(group_id=group.id, user_id=user.id)
                new_group_assoc.save_to_db(db)
                return render_template("group.html", group=group, create_pairs_form=create_pairs_form, form=invite_user_to_group_form)
            else:

                new_invite = EmailInvite(
                    timestamp=datetime.now(),
                    invited_email=invite_user_to_group_form.email.data,
                    group_id=group.id
                )

                new_invite.save_to_db(db)

                to_email = new_invite.invited_email
                admin_first_name = current_user.first_name
                group_name = group.name
                task = celery.send_task("user.invite", (
                    to_email,
                    admin_first_name,
                    group_name
                    )
                )

                if task.status == "PENDING":
                    return render_template("group.html",
                        message=f"{invite_user_to_group_form.email.data} has been invited to create an account and join this group!",
                        group=group,
                        create_pairs_form=create_pairs_form,
                        form=invite_user_to_group_form
                    )

    group_id = request.args.get("group_id")
    if group_id:
        group = Group.query.filter_by(id=group_id).first()
        if group.is_admin(current_user):
            return render_template("group.html",
            create_pairs_form=create_pairs_form,
            group=group,
            form=invite_user_to_group_form
        )
    groups = [i.group for i in current_user.groups]
    return render_template("my_groups.html",
        groups=groups,
        create_pairs_form=create_pairs_form,
        form=create_group_form)


@app.route("/my_groups", methods=["GET", "POST"])
@login_required
def my_groups():
    form = CreateGroupForm()
    leave_group_form = LeaveGroupForm()
    groups = [i.group for i in current_user.groups]

    if request.method == "POST":
        if leave_group_form.validate_on_submit():
            group_name = leave_group_form.group_name.data
            print(leave_group_form)
            print(group_name)
            group = Group.query.filter_by(name=group_name).first()

            group_assoc_with_user = GroupsAndUsersAssociation.query.filter_by(group=group, user=current_user).first()
            group_assoc_with_user.delete_from_db(db)
            return redirect("my_groups")
    return render_template("my_groups.html", groups=groups, form=form, leave_group_form=leave_group_form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/profile")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user.verify_hash(form.password.data, user.password):
            login_user(user)
            if user.admin:
                return redirect("/admin")
            else:
                return redirect("/profile")

    return render_template("login.html", form=form)


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    form = LoginForm()
    return render_template("login.html", form=form)


@app.route("/register", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect("/profile")

    form = SignUpForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            user = User(
                username=form.username.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                password=form.password.data,
                email=form.email.data,
            )

            user.save_to_db(db)
            login_user(user)

            invite = EmailInvite.query.filter_by(invited_email=user.email).first()
            if invite:
                new_group_assoc = GroupsAndUsersAssociation(group_id=invite.group_id, user_id=user.id)
                new_group_assoc.save_to_db(db)

                invite.delete_from_db(db)

                return redirect("my_groups")
            return redirect("profile")
    


    return render_template("index.html", form=form)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/profile")
    form = SignUpForm()
    return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, use_reloader=True)
