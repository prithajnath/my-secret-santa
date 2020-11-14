from flask import Flask, render_template, request, redirect, jsonify
from models import db, Group, User
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
    ParticipantLoginForm,
    ProfileEditForm,
    ChangePasswordForm,
)
from random import choice
from kombu.serialization import register
from serializers import UserSchema, GroupSchema

import os
import admin
import requests as r
import json

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
        current_user.participant.hint = hint
        current_user.participant.address = address

        current_user.participant.save_to_db(db)

        return redirect("/profile")
    hint = current_user.participant.hint
    address = current_user.participant.address
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


@app.route("/group", methods=["GET"])
@login_required
def group():
    group_id = request.args.get("group_id")
    group = Group.filter_by(id=group_id).first()
    if group.is_admin(current_user):
        return render_template("group.html", group=group)


@app.route("/login", methods=["GET", "POST"])
def login():
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
            return redirect("profile")

    return render_template("index.html", form=form)


@app.route("/")
def index():
    form = SignUpForm()
    return render_template("index.html", form=form)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, use_reloader=True)
