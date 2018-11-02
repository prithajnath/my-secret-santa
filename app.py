from flask import Flask, render_template, request, redirect, send_from_directory
from models import db, User, Participant
from flask_mail import Mail, Message


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
db.init_app(app)
mail = Mail(app)
admin.register(app, db)


# Routes
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

    return render_template("success.html", data={"first_name":first_name, "last_name":last_name})

    # except:
    #     return render_template("index.html", message="Something went wrong. Please try again :(")

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, use_reloader=True)
