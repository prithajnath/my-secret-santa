from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, HiddenField
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


class LeaveGroupForm(FlaskForm):
    confirmation = TextAreaField("Are you sure? Pleas type the message above to confirm")
    group_name = HiddenField()

class ProfileEditForm(FlaskForm):
    hint = TextAreaField(validators=[InputRequired()])
    address = TextAreaField(validators=[InputRequired()])

class CreateGroupForm(FlaskForm):
    name = TextAreaField(validators=[InputRequired()])

class InviteUserToGroupForm(FlaskForm):
    email = StringField("email", validators=[InputRequired(), Length(min=4, max=100)])

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
