"""
Authentication API endpoints.

Provides JWT-based authentication for the REST API.
"""

import json
import logging
import os
from datetime import datetime

import requests
from flasgger import swag_from
from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import and_, func

from api import api_bp
from api.utils import api_response, api_error
from models import OAuthProviderEnum, Task, User, UserOAuthProfile, db
from sql import AdvisoryLock

logger = logging.getLogger(__name__)


@api_bp.route("/auth/register", methods=["POST"])
@swag_from({
    "tags": ["Auth"],
    "summary": "Register a new user",
    "description": "Create a new user account and receive JWT tokens",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["username", "email", "password", "first_name", "last_name"],
                "properties": {
                    "username": {"type": "string", "minLength": 4, "maxLength": 150, "example": "johndoe"},
                    "email": {"type": "string", "format": "email", "example": "john@example.com"},
                    "password": {"type": "string", "minLength": 8, "maxLength": 80, "example": "securepassword123"},
                    "first_name": {"type": "string", "minLength": 2, "maxLength": 150, "example": "John"},
                    "last_name": {"type": "string", "minLength": 2, "maxLength": 150, "example": "Doe"},
                },
            },
        }
    ],
    "responses": {
        "201": {
            "description": "User created successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "username": {"type": "string"},
                                    "email": {"type": "string"},
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "avatar_url": {"type": "string"},
                                },
                            },
                            "access_token": {"type": "string"},
                            "refresh_token": {"type": "string"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Validation error"},
        "409": {"description": "Username or email already exists"},
    },
    "security": [],
})
def api_register():
    """Register a new user account."""
    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    required_fields = ["username", "email", "password", "first_name", "last_name"]
    for field in required_fields:
        if field not in data:
            return api_error(f"'{field}' is required", 400)

    # Validate field lengths
    if len(data["username"]) < 4 or len(data["username"]) > 150:
        return api_error("Username must be between 4 and 150 characters", 400)
    if len(data["password"]) < 8 or len(data["password"]) > 80:
        return api_error("Password must be between 8 and 80 characters", 400)
    if len(data["first_name"]) < 2 or len(data["first_name"]) > 150:
        return api_error("First name must be between 2 and 150 characters", 400)
    if len(data["last_name"]) < 2 or len(data["last_name"]) > 150:
        return api_error("Last name must be between 2 and 150 characters", 400)

    # Check for existing user
    existing_username = User.query.filter_by(username=data["username"]).first()
    existing_email = User.query.filter_by(email=data["email"]).first()

    if existing_username:
        return api_error("Username already exists", 409)
    if existing_email:
        return api_error("Email already exists", 409)

    # Create new user
    user = User(
        username=data["username"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        password=data["password"],
        email=data["email"],
    )
    user.save_to_db(db)
    user.last_logged_in = datetime.now()
    user.save_to_db(db)

    # Generate tokens
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return api_response(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        201,
    )


@api_bp.route("/auth/login", methods=["POST"])
@swag_from({
    "tags": ["Auth"],
    "summary": "Login",
    "description": "Authenticate with username and password to receive JWT tokens",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["username", "password"],
                "properties": {
                    "username": {"type": "string", "example": "johndoe"},
                    "password": {"type": "string", "example": "securepassword123"},
                },
            },
        }
    ],
    "responses": {
        "200": {
            "description": "Login successful",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "username": {"type": "string"},
                                    "email": {"type": "string"},
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "avatar_url": {"type": "string"},
                                    "admin": {"type": "boolean"},
                                },
                            },
                            "access_token": {"type": "string"},
                            "refresh_token": {"type": "string"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Missing credentials"},
        "401": {"description": "Invalid username or password"},
    },
    "security": [],
})
def api_login():
    """Login and receive JWT tokens."""
    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    if not data.get("username") or not data.get("password"):
        return api_error("Username and password are required", 400)

    user = User.query.filter_by(username=data["username"]).first()

    if not user:
        return api_error("Invalid username or password", 401)

    if not user.verify_hash(data["password"], user.password):
        return api_error("Invalid username or password", 401)

    user.last_logged_in = datetime.now()
    user.save_to_db(db)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return api_response(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
                "admin": user.admin,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )


@api_bp.route("/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
@swag_from({
    "tags": ["Auth"],
    "summary": "Refresh access token",
    "description": "Get a new access token using a valid refresh token",
    "responses": {
        "200": {
            "description": "New access token generated",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string"},
                        },
                    },
                },
            },
        },
        "401": {"description": "Invalid or expired refresh token"},
    },
})
def api_refresh():
    """Get a new access token using a refresh token."""
    identity = get_jwt_identity()
    access_token = create_access_token(identity=str(identity))
    return api_response({"access_token": access_token})


@api_bp.route("/auth/logout", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Auth"],
    "summary": "Logout",
    "description": "Logout the current user",
    "responses": {
        "200": {
            "description": "Successfully logged out",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "example": "Successfully logged out"},
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
    },
})
def api_logout():
    """Logout the current user."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if user:
        user.last_logged_out = datetime.now()
        user.save_to_db(db)

    return api_response({"message": "Successfully logged out"})


@api_bp.route("/auth/reset-password", methods=["POST"])
@swag_from({
    "tags": ["Auth"],
    "summary": "Request password reset",
    "description": "Request a password reset email. A temporary password will be sent to the email if it exists.",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["email"],
                "properties": {
                    "email": {"type": "string", "format": "email", "example": "john@example.com"},
                },
            },
        }
    ],
    "responses": {
        "200": {
            "description": "Reset request processed",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                        },
                    },
                },
            },
        },
        "429": {"description": "Too many reset attempts"},
    },
    "security": [],
})
def api_reset_password():
    """Request a password reset."""
    from app import celery

    data = request.get_json()

    if not data or "email" not in data:
        return api_error("Email is required", 400)

    email = data["email"]
    user = User.query.filter_by(email=email).first()

    if not user:
        # Don't reveal whether user exists
        return api_response(
            {"message": "If the email exists, a reset link will be sent"}
        )

    # Check for currently running reset attempt
    currently_running = Task.query.filter(
        and_(
            Task.payload["email"].as_string() == user.email,
            Task.name == "reset_user_password",
            Task.status == "starting",
        )
    ).first()

    if currently_running:
        return api_error("Password reset already in progress", 429)

    # Check reset attempt limit
    password_reset_attempts = Task.query.filter(
        and_(
            Task.payload["email"].as_string() == user.email,
            Task.name == "reset_user_password",
            Task.status == "finished",
        )
    ).all()

    if len(password_reset_attempts) >= 3:
        last_reset_date = (
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

        if (datetime.now() - last_reset_date).days < 30:
            return api_error("Too many reset attempts. Try again in a few days.", 429)
        else:
            for attempt in password_reset_attempts:
                attempt.delete_from_db(db)

    with AdvisoryLock(engine=db.engine, lock_key=user.email).grab_lock() as locked:
        lock, session = locked
        if lock:
            new_attempt = Task(
                name="reset_user_password",
                payload={"email": user.email},
                started_at=datetime.now(),
                status="starting",
            )
            session.add(new_attempt)
        else:
            return api_error("Too many concurrent reset attempts", 429)

    celery.send_task("user.reset_password", (user.email,))

    return api_response({"message": "If the email exists, a reset link will be sent"})


@api_bp.route("/auth/change-password", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Auth"],
    "summary": "Change password",
    "description": "Change the current user's password",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["current_password", "new_password"],
                "properties": {
                    "current_password": {"type": "string", "example": "oldpassword123"},
                    "new_password": {"type": "string", "minLength": 8, "maxLength": 80, "example": "newpassword456"},
                },
            },
        }
    ],
    "responses": {
        "200": {
            "description": "Password changed successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "example": "Password changed successfully"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Validation error"},
        "401": {"description": "Current password is incorrect"},
    },
})
def api_change_password():
    """Change the current user's password."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    required = ["current_password", "new_password"]
    for field in required:
        if field not in data:
            return api_error(f"'{field}' is required", 400)

    if len(data["new_password"]) < 8 or len(data["new_password"]) > 80:
        return api_error("New password must be between 8 and 80 characters", 400)

    if not user.verify_hash(data["current_password"], user.password):
        return api_error("Current password is incorrect", 401)

    user.set_password(data["new_password"])
    user.save_to_db(db)

    return api_response({"message": "Password changed successfully"})


# =============================================================================
# OAuth Endpoints
# =============================================================================

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


@api_bp.route("/auth/oauth/google/url", methods=["GET"])
@swag_from({
    "tags": ["Auth"],
    "summary": "Get Google OAuth URL",
    "description": "Get the Google OAuth authorization URL. The frontend should redirect the user to this URL to initiate the OAuth flow.",
    "parameters": [
        {
            "name": "redirect_uri",
            "in": "query",
            "type": "string",
            "required": True,
            "description": "The URI where Google should redirect after authorization (must be registered in Google Console)",
            "example": "https://myapp.com/oauth/callback",
        },
        {
            "name": "state",
            "in": "query",
            "type": "string",
            "required": False,
            "description": "Optional state parameter to pass through the OAuth flow (e.g., for deep linking)",
        },
    ],
    "responses": {
        "200": {
            "description": "OAuth URL generated",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "oauth_url": {"type": "string", "description": "URL to redirect user to"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Missing redirect_uri parameter"},
    },
    "security": [],
})
def api_google_oauth_url():
    """Generate Google OAuth authorization URL for frontend."""
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state", "")

    if not redirect_uri:
        return api_error("'redirect_uri' query parameter is required", 400)

    if not GOOGLE_CLIENT_ID:
        return api_error("Google OAuth is not configured", 500)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join([
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
        ]),
        "access_type": "offline",
        "prompt": "consent",
    }

    if state:
        params["state"] = state

    from urllib.parse import urlencode
    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    return api_response({"oauth_url": oauth_url})


@api_bp.route("/auth/oauth/google/callback", methods=["POST"])
@swag_from({
    "tags": ["Auth"],
    "summary": "Exchange Google OAuth code for JWT tokens",
    "description": "Exchange the authorization code received from Google OAuth callback for JWT access and refresh tokens. Creates a new user account if one doesn't exist for the Google email.",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["code", "redirect_uri"],
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Authorization code from Google OAuth callback",
                    },
                    "redirect_uri": {
                        "type": "string",
                        "description": "The same redirect_uri used when generating the OAuth URL",
                        "example": "https://myapp.com/oauth/callback",
                    },
                },
            },
        }
    ],
    "responses": {
        "200": {
            "description": "OAuth successful, JWT tokens returned",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "user": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "username": {"type": "string"},
                                    "email": {"type": "string"},
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "avatar_url": {"type": "string"},
                                    "is_new_user": {"type": "boolean", "description": "True if account was just created"},
                                },
                            },
                            "access_token": {"type": "string"},
                            "refresh_token": {"type": "string"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Missing code or redirect_uri"},
        "401": {"description": "Invalid authorization code"},
        "500": {"description": "Google OAuth not configured or Google API error"},
    },
    "security": [],
})
def api_google_oauth_callback():
    """Exchange Google OAuth authorization code for JWT tokens."""
    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    code = data.get("code")
    redirect_uri = data.get("redirect_uri")

    if not code:
        return api_error("'code' is required", 400)
    if not redirect_uri:
        return api_error("'redirect_uri' is required", 400)

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return api_error("Google OAuth is not configured", 500)

    # Exchange code for tokens
    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )

        if token_response.status_code != 200:
            logger.error(f"Google token exchange failed: {token_response.content}")
            return api_error("Invalid authorization code", 401)

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")

        if not access_token:
            return api_error("Failed to get access token from Google", 401)

    except requests.RequestException as e:
        logger.error(f"Google token exchange request failed: {e}")
        return api_error("Failed to communicate with Google", 500)

    # Get user info from Google
    try:
        user_response = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            params={"alt": "json", "access_token": access_token},
            headers={"Authorization": f"Bearer {id_token}"} if id_token else {},
            timeout=10,
        )

        if user_response.status_code != 200:
            logger.error(f"Google user info failed: {user_response.content}")
            return api_error("Failed to get user info from Google", 500)

        google_user = user_response.json()

    except requests.RequestException as e:
        logger.error(f"Google user info request failed: {e}")
        return api_error("Failed to communicate with Google", 500)

    email = google_user.get("email")
    google_id = google_user.get("id")
    first_name = google_user.get("given_name", "")
    last_name = google_user.get("family_name", "")
    avatar_url = google_user.get("picture", "")

    if not email:
        return api_error("Could not get email from Google", 500)

    is_new_user = False

    # Check if user exists
    user = User.query.filter_by(email=email).first()

    if user:
        # User exists - check/update OAuth profile
        oauth_profile = UserOAuthProfile.query.filter_by(
            user_id=user.id, vendor=OAuthProviderEnum.GOOGLE
        ).first()

        if oauth_profile:
            # Update avatar if changed
            if oauth_profile.avatar_url != avatar_url:
                oauth_profile.avatar_url = avatar_url
            oauth_profile.save_to_db(db)
        else:
            # First time using Google OAuth for existing user
            oauth_profile = UserOAuthProfile(
                id=google_id,
                user_id=user.id,
                vendor=OAuthProviderEnum.GOOGLE,
                avatar_url=avatar_url,
            )
            oauth_profile.save_to_db(db)
    else:
        # Create new user
        is_new_user = True

        # Generate unique username from first name
        base_username = first_name.lower() if first_name else email.split("@")[0]
        username = base_username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        user.save_to_db(db)

        # Create OAuth profile
        oauth_profile = UserOAuthProfile(
            id=google_id,
            user_id=user.id,
            vendor=OAuthProviderEnum.GOOGLE,
            avatar_url=avatar_url,
        )
        oauth_profile.save_to_db(db)

    # Update last login
    user.last_logged_in = datetime.now()
    user.save_to_db(db)

    # Generate JWT tokens
    jwt_access_token = create_access_token(identity=str(user.id))
    jwt_refresh_token = create_refresh_token(identity=str(user.id))

    return api_response({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
            "is_new_user": is_new_user,
        },
        "access_token": jwt_access_token,
        "refresh_token": jwt_refresh_token,
    })
