from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    TextAreaField,
    HiddenField,
    SubmitField,
)
from wtforms.validators import InputRequired, Length


class SignUpForm(FlaskForm):
    username = StringField(
        "username", validators=[InputRequired(), Length(min=4, max=150)]
    )
    first_name = StringField(
        "first name", validators=[InputRequired(), Length(min=2, max=150)]
    )
    last_name = StringField(
        "last name", validators=[InputRequired(), Length(min=2, max=150)]
    )
    email = StringField("email", validators=[InputRequired(), Length(min=4, max=100)])
    password = PasswordField(
        "password", validators=[InputRequired(), Length(min=8, max=80)]
    )


class LoginForm(FlaskForm):
    username = StringField(
        "username", validators=[InputRequired(), Length(min=4, max=150)]
    )
    password = PasswordField(
        "password", validators=[InputRequired(), Length(min=8, max=80)]
    )
    remember = BooleanField("remember")


class PairForm(FlaskForm):
    message = TextAreaField("Admin message")


class KickUserForm(FlaskForm):
    username = TextAreaField("User username")
    submit_kick_user_form = SubmitField("Submit")


class LeaveGroupForm(FlaskForm):
    confirmation = TextAreaField(
        "Are you sure? Pleas type the message above to confirm"
    )
    group_name = HiddenField()
    submit_leave_group_form = SubmitField("Submit")


class CreatePairsForm(FlaskForm):
    confirmation = TextAreaField(
        "Are you sure? This will send emails to everyone in this group. Type 'yes' to continue"
    )
    submit_create_pairs_form = SubmitField("Submit")


class ResetPasswordForm(FlaskForm):
    email = StringField("email", validators=[InputRequired(), Length(min=4, max=100)])


class ProfileEditForm(FlaskForm):
    hint = TextAreaField(validators=[InputRequired()])
    address = TextAreaField(validators=[InputRequired()])
    first_name = StringField(
        "first name", validators=[InputRequired(), Length(min=2, max=150)]
    )
    last_name = StringField(
        "last name", validators=[InputRequired(), Length(min=2, max=150)]
    )


class CreateGroupForm(FlaskForm):
    name = TextAreaField(validators=[InputRequired()])
    submit_create_group_form = SubmitField("Submit")


class InviteUserToGroupForm(FlaskForm):
    email = StringField("email", validators=[InputRequired(), Length(min=4, max=100)])
    submit_invite_form = SubmitField("Submit")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "password", validators=[InputRequired(), Length(min=8, max=80)]
    )
    new_password = PasswordField(
        "password", validators=[InputRequired(), Length(min=8, max=80)]
    )
    new_password_again = PasswordField(
        "password", validators=[InputRequired(), Length(min=8, max=80)]
    )
