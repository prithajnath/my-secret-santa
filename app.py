import logging
import os

import sentry_sdk
from celery import Celery
from flask import Flask, jsonify, redirect, request
from flask_login import LoginManager
from flask_migrate import Migrate
from flasgger import Swagger
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect

import admin
from api.utils import api_error
from models import User, db
from serializers import ma
from commands import register_commands

app = Flask(__name__)
app.config.update(
    dict(
        DEBUG=False if os.environ.get("ENV") == "production" else True,
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        # JWT Configuration
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", os.environ.get("SECRET_KEY")),
        JWT_ACCESS_TOKEN_EXPIRES=3600,  # 1 hour
        JWT_REFRESH_TOKEN_EXPIRES=2592000,  # 30 days
        # The session cookie only carries the admin panel login
        SESSION_COOKIE_SECURE=os.environ.get("ENV") == "production",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
)

csrf = CSRFProtect(app)

db.init_app(app)
ma.init_app(app)
admin.register(app)
login_manager = LoginManager()
login_manager.init_app(app)

# JWT setup
jwt = JWTManager(app)

# Register API blueprint and exempt from CSRF
from api import api_bp

app.register_blueprint(api_bp)
csrf.exempt(api_bp)

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: rule.rule.startswith("/api"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs/",
}

swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "My Secret Santa API",
        "description": "REST API for the Secret Santa application",
        "version": "1.0.0",
        "contact": {
            "name": "API Support",
        },
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header using the Bearer scheme. Example: 'Bearer {token}'",
        }
    },
    "security": [{"Bearer": []}],
    "tags": [
        {"name": "Auth", "description": "Authentication endpoints"},
        {"name": "Users", "description": "User profile endpoints"},
        {"name": "Groups", "description": "Group management endpoints"},
        {"name": "Messages", "description": "Messaging endpoints"},
        {"name": "Santa", "description": "Secret Santa relationship endpoints"},
        {"name": "Invites", "description": "Invite management endpoints"},
        {"name": "Issues", "description": "Issue reporting endpoints"},
        {"name": "Geo", "description": "Address autocomplete endpoints"},
    ],
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)


# Request headers that carry credentials and must never be written to logs
SENSITIVE_HEADERS = {"authorization", "cookie"}


def _loggable_headers():
    return {
        key: "<redacted>" if key.lower() in SENSITIVE_HEADERS else value
        for key, value in request.headers.items()
    }


# JWT error handlers
# These are routine 401s (expired sessions, logged-out clients), so they are logged below
# ERROR: Sentry turns ERROR log records into issues
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    app.logger.info(f"JWT EXPIRED - Headers: {_loggable_headers()}")
    app.logger.info(f"JWT EXPIRED - Payload: {jwt_payload}")
    return (
        jsonify({"success": False, "error": {"message": "Token has expired"}}),
        401,
    )


@jwt.invalid_token_loader
def invalid_token_callback(error):
    app.logger.warning(f"JWT INVALID - Error: {error}")
    app.logger.warning(f"JWT INVALID - Headers: {_loggable_headers()}")
    return (
        jsonify({"success": False, "error": {"message": "Invalid token"}}),
        401,
    )


@jwt.unauthorized_loader
def missing_token_callback(error):
    app.logger.info(f"JWT MISSING - Error: {error}")
    app.logger.info(f"JWT MISSING - Headers: {_loggable_headers()}")
    return (
        jsonify(
            {"success": False, "error": {"message": "Authorization header is missing"}}
        ),
        401,
    )


celery = Celery("tasks", broker=os.environ.get("CELERY_BROKER_URL"))

if os.getenv("ENV") == "production":
    logger = logging.getLogger("gunicorn.error")
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logger.level)
else:
    logger = app.logger

migrate = Migrate(app, db)
register_commands(app, db)

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

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(f"{admin.LOGIN_URL}?next={request.path}")


# The web app lives in the frontend; this service only serves /api and /admin
@app.route("/")
def index():
    return redirect(os.getenv("FRONTEND_URL", "https://app.mysecretsanta.io"))


@app.errorhandler(404)
def not_found(error):
    return api_error("Not found", 404)


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
