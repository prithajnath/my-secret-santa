"""
User profile API endpoints.
"""

import re
from datetime import datetime

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from api import api_bp
from api.utils import (
    api_error,
    api_response,
    serialize_address_components,
    serialize_user,
)
from models import User, all_latest_pairs_view, db

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def apply_address_components(user, components):
    """
    Validate and store a structured US address on the user.

    Returns an error message, or None on success. Passing None clears the address.
    """
    if components is None:
        user.address = None
        user.address_line1 = user.address_line2 = user.city = user.state = user.zip = None
        user.location = None
        user.geocode_status = None
        user.geocoded_at = None
        return None

    if not isinstance(components, dict):
        return "address_components must be an object"

    line1 = (components.get("address_line1") or "").strip()
    line2 = (components.get("address_line2") or "").strip() or None
    city = (components.get("city") or "").strip()
    state = (components.get("state") or "").strip().upper()
    zip_code = (components.get("zip") or "").strip()

    if not line1 or len(line1) > 200:
        return "address_line1 is required (max 200 characters)"
    if line2 and len(line2) > 200:
        return "address_line2 must be at most 200 characters"
    if not city or len(city) > 100:
        return "city is required (max 100 characters)"
    if state not in US_STATES:
        return "state must be a 2-letter US state code"
    if not ZIP_RE.match(zip_code):
        return "zip must be a 5-digit US ZIP code (optionally ZIP+4)"

    lat, lon = components.get("lat"), components.get("lon")
    has_coordinates = lat is not None and lon is not None
    if has_coordinates:
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return "lat and lon must be numbers"
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return "lat/lon out of range"

    display = ", ".join(part for part in (line1, line2, city) if part) + f", {state} {zip_code}"
    if len(display) > 200:
        return "Address is too long"

    user.address = display
    user.address_line1, user.address_line2 = line1, line2
    user.city, user.state, user.zip = city, state, zip_code
    if has_coordinates:
        # Coordinates come from the autocomplete suggestion the user picked
        user.location = f"SRID=4326;POINT({lon} {lat})"
        user.geocode_status = "autocomplete"
        user.geocoded_at = datetime.now()
    else:
        user.location = None
        user.geocode_status = "pending"
        user.geocoded_at = None
    return None


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
                    "address": {"type": "string", "example": "456 Oak Avenue, City", "description": "Legacy free-text address. Ignored when address_components is sent"},
                    "address_components": {
                        "type": "object",
                        "description": "Structured US address, typically a suggestion from GET /geo/autocomplete. Send null to clear",
                        "properties": {
                            "address_line1": {"type": "string", "example": "1554 Midway Parkway"},
                            "address_line2": {"type": "string", "example": "Apt 358"},
                            "city": {"type": "string", "example": "St Paul"},
                            "state": {"type": "string", "example": "MN"},
                            "zip": {"type": "string", "example": "55108"},
                            "lat": {"type": "number", "example": 44.98},
                            "lon": {"type": "number", "example": -93.17},
                        },
                    },
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

    if "address_components" in data:
        error = apply_address_components(user, data["address_components"])
        if error:
            return api_error(error, 400)
    elif "address" in data:
        # Legacy free-text address: drop the structured fields and queue it for geocoding
        address = (data["address"] or "").strip()
        if len(address) > 200:
            return api_error("Address must be at most 200 characters", 400)
        apply_address_components(user, None)
        if address:
            user.address = address
            user.geocode_status = "pending"

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
            "address_components": serialize_address_components(target_user),
        }
    )
