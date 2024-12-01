import logging
import os
import re
import urllib.parse
from collections import namedtuple
from datetime import datetime
from random import choices

import maya
import sentry_sdk
from celery import Celery
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_bootstrap import Bootstrap
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import and_, func, or_

import admin
from forms import (
    ChangePasswordForm,
    CreateGroupForm,
    CreatePairsForm,
    InviteUserToGroupForm,
    IssueReportForm,
    KickUserForm,
    LeaveGroupForm,
    LoginForm,
    ProfileEditForm,
    ResetPasswordForm,
    SignUpForm,
)
from lib.oauth.google import Google
from models import (
    EmailInvite,
    Group,
    GroupMessage,
    GroupPairReveals,
    GroupsAndUsersAssociation,
    Issue,
    Message,
    OAuthProviderEnum,
    Pair,
    PairCreationStatus,
    Task,
    User,
    UserOAuthProfile,
    all_admin_materialized_view,
    all_latest_pairs_view,
    db,
)
from serializers import ma
from sql import AdvisoryLock

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

csrf = CSRFProtect(app)

Bootstrap(app)
db.init_app(app)
ma.init_app(app)
mail = Mail(app)
admin.register(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
csrf.init_app(app)

celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

if os.getenv("ENV") == "production":
    logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)
else:
    logger = app.logger

migrate = Migrate(app, db)

# sentry
if os.getenv("ENV") == "production":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_API_KEY"),
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        _experiments={
            # Set continuous_profiling_auto_start to True
            # to automatically start the profiler on when
            # possible.
            "continuous_profiling_auto_start": True,
        },
    )

OAUTH_CLIENTS = {
    "google": Google(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(f"/login?next={request.path}")


# Routes


@app.route("/google_oauth", methods=["GET", "POST"])
def google_oauth():
    code = request.args.get("code")
    state = request.args.get("state")
    google_oauth_client = OAUTH_CLIENTS["google"]
    google_user = google_oauth_client.user_data(code=code)
    email = google_user["email"]
    logger.info(google_user)

    logger.info(state)
    redirect_url = "/"
    if state:
        if "invite" in state:
            next_url = urllib.parse.unquote(state)
            redirect_url = next_url

    # Check if we have a user with this email in the first place
    if user := User.query.filter_by(email=email).first():
        # They have logged in with Google befrore
        if user_google_profile := UserOAuthProfile.query.filter_by(
            user_id=user.id, vendor=OAuthProviderEnum.GOOGLE
        ).first():
            # If they have, check their avatar_url and log them in
            if user_google_profile.avatar_url != google_user["avatar_url"]:
                user_google_profile.avatar_url = google_user["avatar_url"]
            user_google_profile.save_to_db(db)  # This is to update last_logged_in

            login_user(user)
            return redirect(redirect_url)
        else:
            # They're signing up/logging in with Google for the first time
            user_google_profile = UserOAuthProfile(
                user_id=user.id,
                id=google_user["id"],
                avatar_url=google_user["avatar_url"],
                vendor=OAuthProviderEnum.GOOGLE,
            )

            user_google_profile.save_to_db(db)

            login_user(user)

            return redirect(redirect_url)

    # If we don't recognize this user,
    # we can create a new account without a password because Google has already authenticated them
    user = User(
        email=email,
    )

    user.username = google_user["first_name"]
    user.first_name = google_user["first_name"]
    user.last_name = google_user["last_name"]
    user.save_to_db(db)

    user_google_profile = UserOAuthProfile(
        user_id=user.id,
        id=google_user["id"],
        avatar_url=google_user["avatar_url"],
        vendor=OAuthProviderEnum.GOOGLE,
    )

    user_google_profile.save_to_db(db)

    login_user(user)

    return redirect(redirect_url)


@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            currently_running_reset_attempt = Task.query.filter(
                and_(
                    Task.payload["email"].as_string() == user.email,
                    Task.name == "reset_user_password",
                    Task.status == "starting",
                )
            ).first()

            if currently_running_reset_attempt:
                message = "Already processing recent password reset"
                return render_template(
                    "reset_password.html", form=form, message=message
                )

            password_reset_attempts = Task.query.filter(
                and_(
                    Task.payload["email"].as_string() == user.email,
                    Task.name == "reset_user_password",
                    Task.status == "finished",
                )
            ).all()
            if len(password_reset_attempts) < 3:
                with AdvisoryLock(
                    engine=db.engine, lock_key=user.email
                ).grab_lock() as locked_session:
                    lock, session = locked_session
                    if lock:
                        new_attempt = Task(
                            name="reset_user_password",
                            payload={
                                "email": user.email,
                            },
                            started_at=datetime.now(),
                            status="starting",
                        )
                        session.add(new_attempt)

                    else:
                        message = "Too many reset attempts at the same time!"
                        return render_template(
                            "/reset_password", form=form, message=message
                        )
                # Send task to celery ONLY AFTER we have
                # 1. Committed the new row to db
                # 2. Released the lock

                celery.send_task("user.reset_password", (user.email,))

                message = f"A temporary password will be sent to {user.email} shortly"
                return render_template(
                    "reset_password.html", form=form, message=message
                )
            else:
                last_reset_attempt_date = (
                    Task.query.with_entities(func.max(Task.started_at))
                    .filter(
                        and_(
                            Task.payload["email"].as_string() == user.email,
                            Task.name == "reset_user_password",
                            Task.status == "finished",
                        )
                    )
                    .first()[0]
                )
                today = datetime.now()

                if (today - last_reset_attempt_date).days < 30:
                    message = "Too many reset attempts recently. Check back again after a few days"
                    return render_template(
                        "reset_password.html", form=form, message=message
                    )
                else:
                    for attempt in password_reset_attempts:
                        attempt.delete_from_db(db)

                    with AdvisoryLock(
                        engine=db.engine, lock_key=user.email
                    ).grab_lock() as locked_session:
                        lock, session = locked_session
                        if lock:
                            new_attempt = Task(
                                payload={
                                    "name": "reset_user_password",
                                    "email": user.email,
                                },
                                started_at=datetime.now(),
                                status="starting",
                            )

                            session.add(new_attempt)
                        else:
                            message = "Too many reset attempts at the same time!"
                            return render_template(
                                "reset_password", form=form, message=message
                            )

                    # Send task to celery ONLY AFTER we have
                    # 1. Committed the new row to db
                    # 2. Released the lock

                    celery.send_task("user.reset_password", (user.email,))

                    message = (
                        f"A temporary password will be sent to {user.email} shortly"
                    )
                    return render_template(
                        "reset_password.html", form=form, message=message
                    )

        message = f"No user with the email {form.email.data} was found"
        return render_template("reset_password.html", form=form, message=message)
    return render_template("reset_password.html", form=form)


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
        first_name = form.first_name.data
        last_name = form.last_name.data
        current_user.hint = hint
        current_user.address = address
        current_user.first_name = first_name
        current_user.last_name = last_name

        current_user.save_to_db(db)

        return redirect("/profile")
    hint = current_user.hint
    address = current_user.address
    return render_template("edit_profile.html", form=form, hint=hint, address=address)


@app.route("/profile/<username>", methods=["GET"])
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile(username=None):
    if username:
        user = User.query.filter_by(username=username).first()
        # Only reveal profile info if the current user is the secret santa of this username in some group
        secret_santees = all_latest_pairs_view.query.filter_by(
            giver_username=current_user.username
        ).all()

        if username in [row.receiver_username for row in secret_santees]:
            return render_template("profile.html", user=user)
        else:
            return render_template(
                "profile.html",
                not_allowed="Oops, you're not allowed to view this profile!",
            )
    return render_template("profile.html")


@app.route("/kick", methods=["POST"])
@login_required
def kick():
    group_id = request.args.get("group_id")
    kick_user_form = KickUserForm()

    if kick_user_form.validate() and kick_user_form.username.data:
        association = (
            db.session.query(GroupsAndUsersAssociation)
            .select_from(GroupsAndUsersAssociation)
            .join(User)
            .filter(
                and_(
                    User.username == kick_user_form.username.data,
                    GroupsAndUsersAssociation.group_id == group_id,
                )
            )
            .first()
        )
        association.delete_from_db(db)

        return redirect(f"/groups?group_id={group_id}")


@app.route("/santa", methods=["GET", "POST"])
@login_required
def santa():
    all_pairs = all_latest_pairs_view.query.filter(
        or_(
            all_latest_pairs_view._view.giver_username == current_user.username,
            all_latest_pairs_view._view.receiver_username == current_user.username,
        )
    ).all()

    Santa = namedtuple("Santa", "group channel_id")
    santas = [
        Santa(Group.query.filter_by(name=i.group_name).first(), i.channel_id)
        for i in all_pairs
        if i.receiver_username == current_user.username
    ]
    Santee = namedtuple("Santee", "group_name receiver_username channel_id")
    santees = [
        Santee(i.group_name, i.receiver_username, i.channel_id)
        for i in all_pairs
        if i.giver_username == current_user.username
    ]

    return render_template("santa.html", santas=santas, santees=santees)


@app.route("/groups", methods=["GET", "POST"])
@login_required
def group():
    # Forms
    create_group_form = CreateGroupForm()
    leave_group_form = LeaveGroupForm()
    invite_user_to_group_form = InviteUserToGroupForm()
    create_pairs_form = CreatePairsForm()
    kick_user_form = KickUserForm()

    # Args
    message = request.args.get("message")

    if request.method == "POST":
        if (
            create_group_form.submit_create_group_form.data
            and create_group_form.validate()
        ):
            group_name = create_group_form.name.data
            group = Group.query.filter_by(name=group_name).first()
            if group:
                return redirect(
                    url_for(
                        ".group",
                        message=f"Group with the name {group_name} already exists",
                    )
                )
            new_group = Group(name=group_name)
            new_group.save_to_db(db)
            new_group_assoc = GroupsAndUsersAssociation(
                group=new_group, user=current_user, group_admin=True
            )
            new_group_assoc.save_to_db(db)

            # TODO: @prithajnath
            # We shouldn't have to do this here. This should be taken care of by the right SQLALchemy hook
            all_admin_materialized_view.refresh()

            return redirect(url_for(".group", group_id=new_group.id))

        if (
            leave_group_form.submit_leave_group_form.data
            and leave_group_form.validate()
        ):
            group_name = leave_group_form.group_name.data
            logger.info(leave_group_form)
            logger.info(group_name)
            group = Group.query.filter_by(name=group_name).first()

            group_assoc_with_user = GroupsAndUsersAssociation.query.filter_by(
                group=group, user=current_user
            ).first()
            group_assoc_with_user.delete_from_db(db)
            return redirect(url_for(".group"))

        if (
            create_pairs_form.submit_create_pairs_form.data
            and create_pairs_form.validate()
        ):
            logger.info(create_pairs_form.submit_create_pairs_form.data)
            group_id = request.args.get("group_id")
            logger.info(f"Creating pairs for {group_id}")
            group = Group.query.filter_by(id=group_id).first()

            currently_running_creation_attempt = PairCreationStatus.query.filter_by(
                group_id=group.id, status="creating"
            ).first()

            if currently_running_creation_attempt:
                message = "Pair creation already in progress"
                return redirect(url_for(".group", message=message, group_id=group_id))

            pair_latest_timestamp = Pair.query.with_entities(
                func.max(Pair.timestamp)
            ).filter_by(group_id=group_id).first()[0] or datetime(1970, 1, 1)

            today = datetime.now()

            delta = today - pair_latest_timestamp
            if delta.days >= 1:
                if group.is_admin(current_user) and current_user.is_authenticated:
                    with AdvisoryLock(
                        engine=db.engine, lock_key=group.name
                    ).grab_lock() as locked_session:
                        lock, session = locked_session
                        if lock:
                            # NOTE: Can't pass SQLAlchemy objects like group* and current_user** here because
                            # they are attached to a different session
                            creation_attempt = Task(
                                started_at=datetime.now(),
                                name="create_pairs",
                                payload={
                                    "group_id": group.id,
                                    "initiator_id": current_user.id,
                                },
                                status="starting",
                            )

                            session.add(creation_attempt)
                        else:
                            message = (
                                "Too many attempts to create pairs at the same time!"
                            )
                            return redirect(
                                url_for(".group", message=message, group_id=group_id)
                            )

                    # Again, only queue messages after lock has been released
                    task = celery.send_task("pair.create_pairs", (group_id,))

                    if task.status == "PENDING":
                        timestamp = maya.MayaDT.from_datetime(datetime.now())
                        message = f"Pair creation has been initiated at {timestamp.__str__()}. Sit tight!"
                        return redirect(
                            url_for(".group", message=message, group_id=group_id)
                        )
            else:
                message = "This group is in cooldown (Pairs were created recently). Please try again in a day"
                return redirect(url_for(".group", message=message, group_id=group_id))

        if (
            invite_user_to_group_form.submit_invite_form.data
            and invite_user_to_group_form.validate()
        ):
            group_id = request.args.get("group_id")
            group = Group.query.filter_by(id=group_id).first()
            user = User.query.filter_by(
                email=invite_user_to_group_form.email.data
            ).first()
            new_invite = EmailInvite(
                timestamp=datetime.now(),
                invited_email=invite_user_to_group_form.email.data,
                code=EmailInvite.generate_code("group"),
                payload=(
                    {"group_id": group.id, "user_id": user.id}
                    if user
                    else {"group_id": group.id}
                ),
            )

            new_invite.save_to_db(db)

            to_email = new_invite.invited_email
            admin_first_name = current_user.first_name
            group_name = group.name

            if not user:
                _task = Task(
                    name="invite_user_to_sign_up",
                    started_at=datetime.now(),
                    status="starting",
                    payload={
                        "to_email": to_email,
                        "admin_first_name": admin_first_name,
                        "invite_code": new_invite.code,
                        "group_name": group_name,
                    },
                )

                _task.save_to_db(db)

                task = celery.send_task(
                    "user.invite_user_to_sign_up",
                    (to_email, admin_first_name, group_name),
                )

                if task.status == "PENDING":
                    return redirect(
                        url_for(
                            ".group",
                            message=f"{invite_user_to_group_form.email.data} has been invited to create an account and join this group!",
                            group_id=group_id,
                            create_pairs_form=create_pairs_form,
                            form=invite_user_to_group_form,
                        )
                    )

            else:
                _task = Task(
                    name="invite_user_to_group",
                    started_at=datetime.now(),
                    status="starting",
                    payload={
                        "to_email": to_email,
                        "admin_first_name": admin_first_name,
                        "invite_code": new_invite.code,
                        "group_name": group_name,
                    },
                )

                _task.save_to_db(db)

                task = celery.send_task(
                    "user.invite_user_to_group",
                    (to_email, admin_first_name, group_name),
                )

                if task.status == "PENDING":
                    return redirect(
                        url_for(
                            ".group",
                            message=f"{invite_user_to_group_form.email.data} has been invited to join this group!",
                            group_id=group_id,
                            create_pairs_form=create_pairs_form,
                            form=invite_user_to_group_form,
                        )
                    )

    group_id = request.args.get("group_id")
    message = request.args.get("message")
    alert = request.args.get("alert")
    group = Group.query.filter_by(id=group_id).first()

    if group:
        if GroupsAndUsersAssociation.query.filter_by(
            group_id=group.id, user_id=current_user.id
        ).first():
            return render_template(
                "group.html",
                create_pairs_form=create_pairs_form,
                invite_user_to_group_form=invite_user_to_group_form,
                kick_user_form=kick_user_form,
                group=group,
                message=message,
                alert=alert,
            )

    GroupPreview = namedtuple("GroupPreview", "id name avatars members")
    groups = []
    for i in current_user.groups:
        group = i.group
        avatars = [j.user.avatar_url for j in group.users]
        groups.append(GroupPreview(group.id, group.name, avatars[:3], len(avatars)))

    return render_template(
        "my_groups.html",
        groups=groups,
        create_group_form=create_group_form,
        leave_group_form=leave_group_form,
        message=message,
        alert=alert,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if next := request.args.get("next"):
            return redirect(next)
        return redirect("/profile")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.verify_hash(form.password.data, user.password):
                login_user(user)
                user.last_logged_in = datetime.now()
                user.save_to_db(db)
                if next := request.args.get("next"):
                    return redirect(next)
                if user.admin:
                    return redirect("/admin")
                else:
                    return redirect("/profile")
            else:
                return redirect(
                    url_for(".login", message=f"Please check your password")
                )
        else:
            return redirect(
                url_for(
                    ".login",
                    message=f"Couldn't find user with username {form.username.data}",
                )
            )
    message = request.args.get("message")

    google_oauth_client = OAUTH_CLIENTS["google"]

    return render_template(
        "login.html",
        message=message,
        form=form,
        oauth_url=google_oauth_client.oauth_url,
    )


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    current_user.last_logged_out = datetime.now()
    current_user.save_to_db(db)
    logout_user()
    form = LoginForm()
    return render_template("login.html", form=form)


@app.route("/invite", methods=["GET"])
@login_required
def invite():
    code = request.args.get("code")

    if invite := EmailInvite.query.filter_by(code=code).first():
        if re.search("\AADMIN-(\d|[A-Z])+\Z", code):
            # An admin invite can ONLY be fpr someone who is already an user
            group_id = invite.payload["group_id"]
            # Check if the user is already in the group
            existing_assoc = GroupsAndUsersAssociation.query.filter_by(
                group_id=group_id, user_id=current_user.id
            ).first()
            if existing_assoc:
                existing_assoc.group_admin = True
                existing_assoc.save_to_db(db)
            else:
                new_group_assoc = GroupsAndUsersAssociation(
                    group_id=group_id, user_id=current_user.id, group_admin=True
                )
                new_group_assoc.save_to_db(db)

        if re.search("\AGROUP-(\d|[A-Z])+\Z", code):
            # A group invite can be for a person who is already a user or someone who is not a user (yet)
            group_id = invite.payload["group_id"]
            if user_id := invite.payload.get("user_id"):
                if user_id != current_user.id:
                    logger.error(f"Wrong invite code used for user {user_id}")
                    flash("The invite code is either incorrect or has expired")
                    return redirect("/profile")

                new_group_assoc = GroupsAndUsersAssociation(
                    group_id=group_id, user_id=current_user.id
                )
                new_group_assoc.save_to_db(db)
            else:
                # This is a new user so we need to find the User object
                user = User.query.filter_by(email=invite.invited_email).first()
                if user.id != current_user.id:
                    logger.error(f"Wrong invite code used for new user {user.email}")
                    flash("The invite code is either incorrect or has expired")
                    return redirect("/profile")
                new_group_assoc = GroupsAndUsersAssociation(
                    group_id=group_id, user_id=user.id
                )
                new_group_assoc.save_to_db(db)

        invite.delete_from_db(db)
        return redirect("/groups")
    else:

        flash("The invite code is either incorrect or has expired")
        return redirect("/profile")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        if next := request.args.get("next"):
            return redirect(next)
        return redirect("/profile")

    form = SignUpForm()
    if request.method == "GET":
        google_oauth_client = OAUTH_CLIENTS["Google"]
        return render_template(
            "index.html", form=form, oauth_url=google_oauth_client.oauth_url
        )

    if form.validate_on_submit():
        username = User.query.filter_by(username=form.username.data).first()
        email = User.query.filter_by(email=form.email.data).first()
        if not username and not email:
            user = User(
                username=form.username.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                password=form.password.data,
                email=form.email.data,
            )

            user.save_to_db(db)
            login_user(user)
            user.last_logged_in = datetime.now()
            user.save_to_db(db)

            if next := request.args.get("next"):
                return redirect(next)

            else:
                return redirect("/groups")
        else:
            return redirect(
                url_for(
                    ".signup", alert="User with that email or username already exists"
                )
            )


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/profile")
    return render_template("landing.html")


@app.route("/signup")
def signup():
    if current_user.is_authenticated:
        return redirect("/profile")
    form = SignUpForm()
    alert = request.args.get("alert")
    google_oauth_client = OAUTH_CLIENTS["google"]
    return render_template(
        "index.html",
        alert=alert,
        form=form,
        oauth_url=google_oauth_client.oauth_url,
    )


# JSON endpoints


@app.route("/group_message", methods=["GET", "POST"])
@login_required
def group_message():
    group_id = request.args.get("group_id")
    if request.method == "POST":
        message = request.json.get("message")

        last_message = (
            GroupMessage.query.filter_by(group_id=group_id)
            .order_by(GroupMessage.created_at.desc())
            .limit(1)
            .first()
        )

        new_message = GroupMessage(
            group_id=group_id,
            sender_id=current_user.id,
            text=message,
            created_at=datetime.now(),
        )

        new_message.save_to_db(db)

        if last_message:
            delta = new_message.created_at - last_message.created_at
        else:
            delta = new_message.created_at - datetime(1970, 1, 1)

        if delta.seconds + delta.days * (60**2) * 24 >= 60 * 15:

            task = Task(
                name="send_group_chat_notifications",
                started_at=datetime.now(),
                status="starting",
                payload={
                    "sender_username": current_user.username,
                    "text": message,
                    "group_id": group_id,
                },
            )

            task.save_to_db(db)

            celery.send_task(
                "user.send_group_chat_notifications",
                (current_user.username, message, group_id),
            )
        else:
            logger.info(f"Too many frquent messages for group {group_id}. Backing off")

        return jsonify(result=True)

    all_messages = (
        GroupMessage.query.filter_by(group_id=group_id)
        .order_by(GroupMessage.created_at)
        .all()
    )

    return jsonify(
        result=[
            {
                "username": message.sender.username,
                "avatar_url": message.sender.avatar_url,
                "first_name": message.sender.first_name,
                "type": (
                    "receiver"
                    if current_user.username == message.sender.username
                    else "sender"
                ),
                "text": message.text,
            }
            for message in all_messages
        ]
    )


@app.route("/santee_message", methods=["GET", "POST"])
@login_required
def santee_message():
    to = request.args.get("to")
    channel_id = request.args.get("channel_id")

    santee = User.query.filter_by(username=to).first()

    if request.method == "POST":
        message = request.json.get("message")
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=santee.id,
            pair_channel_id=channel_id,
            text=message,
            created_at=datetime.now(),
        )

        new_message.save_to_db(db)

        _task = Task(
            name="send_message_notification",
            started_at=datetime.now(),
            status="starting",
            payload={
                "sender_id": current_user.id,
                "receiver_id": santee.id,
                "channel_id": channel_id,
                "text": message,
            },
        )

        _task.save_to_db(db)

        celery.send_task(
            "user.send_message_notification",
            (current_user.id, santee.id, channel_id, message, True),
        )

        return jsonify(result=True)

    messages = (
        Message.query.filter_by(pair_channel_id=channel_id)
        .order_by(Message.created_at)
        .all()
    )

    return jsonify(
        result=[
            (
                "receiver" if message.sender_id == current_user.id else "sender",
                message.text,
            )
            for message in messages
        ]
    )


@app.route("/santa_message", methods=["GET", "POST"])
@login_required
def santa_message():
    channel_id = request.args.get("channel_id")

    secret_santa_for_this_group = (
        all_latest_pairs_view.query.filter_by(channel_id=channel_id)
        .first()
        .giver_username
    )

    secret_santa = User.query.filter_by(username=secret_santa_for_this_group).first()

    if request.method == "POST":
        message = request.json.get("message")
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=secret_santa.id,
            pair_channel_id=channel_id,
            text=message,
            created_at=datetime.now(),
        )

        new_message.save_to_db(db)

        _task = Task(
            name="send_message_notification",
            started_at=datetime.now(),
            status="starting",
            payload={
                "sender_id": current_user.id,
                "receiver_id": secret_santa.id,
                "channel_id": channel_id,
                "text": message,
            },
        )

        _task.save_to_db(db)

        celery.send_task(
            "user.send_message_notification",
            (current_user.id, secret_santa.id, channel_id, message, False),
        )

        return jsonify(result=True)

    messages = (
        Message.query.filter_by(pair_channel_id=channel_id)
        .order_by(Message.created_at)
        .all()
    )

    return jsonify(
        result=[
            (
                "receiver" if message.sender_id == current_user.id else "sender",
                message.text,
            )
            for message in messages
        ]
    )


@app.route("/reveal_toggle", methods=["POST"])
@login_required
def reveal_group_santas():
    group_id = request.json.get("group_id")
    action = request.json.get("action")
    group = Group.query.filter_by(id=group_id).first()
    if group:
        with AdvisoryLock(
            engine=db.engine, lock_key=group.name
        ).grab_lock() as locked_session:
            lock, session = locked_session
            if lock:
                group_in_locked_session = (
                    session.query(Group).filter_by(id=group_id).first()
                )
                timestamp = datetime.now()
                group_reveal_history = GroupPairReveals(
                    group_id=group_id, user_id=current_user.id, timestamp=timestamp
                )
                group_in_locked_session.reveal_latest_pairs = bool(int(action))
                session.add(group_in_locked_session)
                session.add(group_reveal_history)
            else:
                return jsonify(result="too many concurrent attemps!")

        return jsonify(result=action)
    return 404


@app.route("/report_issue", methods=["GET", "POST"])
@login_required
def report_issue():

    form = IssueReportForm()
    if request.method == "POST":

        if form.validate_on_submit():

            new_issue = Issue(
                user_id=current_user.id,
                title=form.issue_title.data,
                description=form.issue_description.data,
            )

            new_issue.save_to_db(db)

            message = "Thank you for your feedback! I'll get back to you as soon as possible :)"
            return render_template("report_an_issue.html", form=form, message=message)
        else:
            error = "Something went wrong. Please refresh the page and try again"
            return render_template("report_an_issue.html", form=form, error=error)

    return render_template("report_an_issue.html", form=form)


@app.route("/reveal_secret_santa", methods=["GET"])
def reveal_secret_santa():
    group_name = request.args.get("group_name")
    secret_santa = all_latest_pairs_view.query.filter_by(
        group_name=group_name, receiver_username=current_user.username
    ).first()

    group = Group.query.filter_by(name=group_name).first()
    users = [i.user.username for i in group.users]
    return jsonify(username=secret_santa.giver_username, randos=choices(users, k=10))


if __name__ == "__main__":
    if os.getenv("ENV") != "production":
        ssl_context = ("cert.pem", "key.pem")
        stream_handler = logging.StreamHandler()
        stream_handler_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        stream_handler.setFormatter(stream_handler_formatter)
        app.logger.setLevel(logging.DEBUG)
        app.logger.addHandler(stream_handler)

        app.run(host="0.0.0.0", port=9000, ssl_context=ssl_context, use_reloader=True)
    else:
        app.run(host="0.0.0.0", port=9000, use_reloader=True)
