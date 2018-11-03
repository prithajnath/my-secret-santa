from flask import Flask, render_template, request, redirect, send_from_directory
from models import db, User, Participant
from flask_mail import Mail, Message
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Length
from flask_bootstrap import Bootstrap

import os
import admin

app = Flask(__name__)
app.config.update(dict(
# email server
    DEBUG = True,
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = 587,
    MAIL_USE_TLS = True,
    MAIL_USE_SSL = False,
    MAIL_USERNAME = f"{os.environ.get('MAIL_USERNAME')}@gmail.com",
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD'),
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI'),
    SQLALCHEMY_TRACK_MODIFICATIONS = True,
    SECRET_KEY = os.environ.get('SECRET_KEY'),
    CSRF_ENABLED = True
))
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
Bootstrap(app)
db.init_app(app)
mail = Mail(app)
admin.register(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember')

def send_email(sender, subject,recipients, template, data):
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
@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user.verify_hash(form.password.data, user.password):
            login_user(user)
            return redirect('/admin')
    return render_template('login.html', form=form)

@app.route("/logout", methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return render_template('index.html')


@app.route("/register", methods=['POST'])
def register():
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    email = request.form['email']
    hint = request.form['hint']
    address = request.form['address']

    participant = Participant.query.filter_by(email=email).first()
    if participant:
        return render_template("index.html", message="You already registered you dumb fuck")

    # try:
    new_participant = Participant(
        first_name=first_name,
        last_name=last_name,
        email=email,
        hint=hint,
        address=address
    )

    new_participant.save_to_db(db)

    if send_email('platts.sec@gmail.com','SECret Confirmation',[email], "confirmation.html", {"first_name":first_name, "address":address}):
        return render_template("success.html", data={"first_name":first_name, "last_name":last_name})
    return render_template("index.html", message="Are you sure that was a valid email? :/")

    # except:
    #     return render_template("index.html", message="Something went wrong. Please try again :(")

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, use_reloader=True)
