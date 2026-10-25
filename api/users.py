"""
User profile API endpoints.
"""

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from api import api_bp
from api.utils import api_error, api_response, serialize_user
from models import User, all_latest_pairs_view, db


@api_bp.route("/users/me", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Users"],
    "summary": "Get current user profile",
    "description": "Get the authenticated user's profile information including private fields",
    "responses": {
        "200": {
            "description": "User profile retrieved successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 1},
                            "username": {"type": "string", "example": "johndoe"},
                            "email": {"type": "string", "example": "john@example.com"},
                            "first_name": {"type": "string", "example": "John"},
                            "last_name": {"type": "string", "example": "Doe"},
                            "avatar_url": {"type": "string"},
                            "hint": {"type": "string", "example": "I like video games"},
                            "address": {"type": "string", "example": "123 Main St"},
                            "admin": {"type": "boolean", "example": False},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
        "404": {"description": "User not found"},
    },
})
def api_get_current_user():
    """Get the current user's profile."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    return api_response(serialize_user(user, include_private=True))


@api_bp.route("/users/me", methods=["PUT"])
@jwt_required()
@swag_from({
    "tags": ["Users"],
    "summary": "Update current user profile",
    "description": "Update the authenticated user's profile information",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "hint": {"type": "string", "example": "I love board games and puzzles"},
                    "address": {"type": "string", "example": "456 Oak Avenue, City"},
                    "first_name": {"type": "string", "minLength": 2, "maxLength": 150, "example": "John"},
                    "last_name": {"type": "string", "minLength": 2, "maxLength": 150, "example": "Doe"},
                },
            },
        }
    ],
    "responses": {
        "200": {
            "description": "Profile updated successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "email": {"type": "string"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "avatar_url": {"type": "string"},
                            "hint": {"type": "string"},
                            "address": {"type": "string"},
                            "admin": {"type": "boolean"},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Validation error"},
        "401": {"description": "Missing or invalid token"},
        "404": {"description": "User not found"},
    },
})
def api_update_current_user():
    """Update the current user's profile."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    # Update allowed fields
    if "hint" in data:
        user.hint = data["hint"]

    if "address" in data:
        user.address = data["address"]

    if "first_name" in data:
        if len(data["first_name"]) < 2 or len(data["first_name"]) > 150:
            return api_error("First name must be between 2 and 150 characters", 400)
        user.first_name = data["first_name"]

    if "last_name" in data:
        if len(data["last_name"]) < 2 or len(data["last_name"]) > 150:
            return api_error("Last name must be between 2 and 150 characters", 400)
        user.last_name = data["last_name"]

    user.save_to_db(db)

    return api_response(serialize_user(user, include_private=True))


@api_bp.route("/users/<username>", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Users"],
    "summary": "Get another user's profile",
    "description": "Get another user's profile. Only accessible if the authenticated user is the secret santa for the requested user in at least one group.",
    "parameters": [
        {
            "name": "username",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Username of the user to retrieve",
        }
    ],
    "responses": {
        "200": {
            "description": "User profile retrieved successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "avatar_url": {"type": "string"},
                            "hint": {"type": "string", "description": "Gift hints from the user"},
                            "address": {"type": "string", "description": "Shipping address"},
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "You are not the secret santa for this user"},
        "404": {"description": "User not found"},
    },
})
def api_get_user(username):
    """
    Get another user's profile.

    Only returns profile information if the current user is the secret santa
    of the requested user in at least one group.
    """
    identity = get_jwt_identity()
    current_user = db.session.get(User, identity)

    if not current_user:
        return api_error("Current user not found", 404)

    target_user = User.query.filter_by(username=username).first()

    if not target_user:
        return api_error("User not found", 404)

    # Check if current user is the secret santa of this user
    secret_santees = all_latest_pairs_view.query.filter_by(
        giver_username=current_user.username
    ).all()

    santee_usernames = [row.receiver_username for row in secret_santees]

    if username not in santee_usernames:
        return api_error(
            "You can only view the profile of someone you are the secret santa for",
            403,
        )

    # Return profile with hint and address (what a secret santa needs)
    return api_response(
        {
            "id": target_user.id,
            "username": target_user.username,
            "first_name": target_user.first_name,
            "last_name": target_user.last_name,
            "avatar_url": target_user.avatar_url,
            "hint": target_user.hint,
            "address": target_user.address,
        }
    )
