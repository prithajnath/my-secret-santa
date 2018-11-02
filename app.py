from flask import Flask, render_template, request, redirect, send_from_directory
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
# app.config.update(dict(
# # email server
#     DEBUG = True,
#     MAIL_SERVER = 'smtp.gmail.com',
#     MAIL_PORT = 587,
#     MAIL_USE_TLS = True,
#     MAIL_USE_SSL = False,
#     MAIL_USERNAME = f"{os.environ.get('MAIL_USERNAME')}@ixisdigital.com",
#     MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
# ))
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'

# Initialize
# mail = Mail(app)
# models.db.init_app(app)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8060, use_reloader=True)
