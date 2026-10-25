"""
Utility functions for the REST API.
"""

from flask import jsonify


def api_response(data, status_code=200):
    """
    Create a standardized successful API response.

    Args:
        data: The data to return in the response
        status_code: HTTP status code (default 200)

    Returns:
        Flask response tuple (response, status_code)
    """
    response = {"success": True, "data": data}
    return jsonify(response), status_code


def api_error(message, status_code=400, errors=None):
    """
    Create a standardized error API response.

    Args:
        message: Error message
        status_code: HTTP status code (default 400)
        errors: Optional dict of field-specific errors

    Returns:
        Flask response tuple (response, status_code)
    """
    response = {"success": False, "error": {"message": message}}

    if errors:
        response["error"]["details"] = errors

    return jsonify(response), status_code


# geocode_status values meaning `location` holds a real coordinate
VERIFIED_GEOCODE_STATUSES = ("autocomplete", "census", "geoapify")


def serialize_address_components(user):
    """Structured address fields. Coordinates are deliberately never included."""
    if not user.address_line1:
        return None
    return {
        "address_line1": user.address_line1,
        "address_line2": user.address_line2,
        "city": user.city,
        "state": user.state,
        "zip": user.zip,
    }


def serialize_user(user, include_private=False):
    """
    Serialize a User object to a dictionary.

    Args:
        user: User model instance
        include_private: Whether to include private fields (email, address)

    Returns:
        Dictionary representation of the user
    """
    data = {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar_url": user.avatar_url,
    }

    if include_private:
        data["email"] = user.email
        data["hint"] = user.hint
        data["address"] = user.address
        data["address_components"] = serialize_address_components(user)
        data["address_verified"] = user.geocode_status in VERIFIED_GEOCODE_STATUSES
        data["admin"] = user.admin
        data["created_at"] = user.created_at.isoformat() if user.created_at else None

    return data


def serialize_group(group, include_members=False):
    """
    Serialize a Group object to a dictionary.

    Args:
        group: Group model instance
        include_members: Whether to include member list

    Returns:
        Dictionary representation of the group
    """
    data = {
        "id": group.id,
        "name": group.name,
        "reveal_latest_pairs": group.reveal_latest_pairs,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "member_count": len(group.users),
    }

    if include_members:
        data["members"] = [
            {
                "user_id": assoc.user.id,
                "username": assoc.user.username,
                "first_name": assoc.user.first_name,
                "last_name": assoc.user.last_name,
                "avatar_url": assoc.user.avatar_url,
                "is_admin": assoc.group_admin,
                "participating": assoc.participating,
            }
            for assoc in group.users
        ]

    return data


def serialize_message(message, current_user_id):
    """
    Serialize a Message object to a dictionary.

    Args:
        message: Message model instance
        current_user_id: ID of the current user (to determine sender/receiver perspective)

    Returns:
        Dictionary representation of the message
    """
    return {
        "id": message.id,
        "text": message.text,
        "direction": "sent" if message.sender_id == current_user_id else "received",
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def serialize_group_message(message, current_user_id):
    """
    Serialize a GroupMessage object to a dictionary.

    Args:
        message: GroupMessage model instance
        current_user_id: ID of the current user

    Returns:
        Dictionary representation of the group message
    """
    return {
        "id": message.id,
        "text": message.text,
        "sender": {
            "id": message.sender.id,
            "username": message.sender.username,
            "first_name": message.sender.first_name,
            "avatar_url": message.sender.avatar_url,
        },
        "is_own_message": message.sender_id == current_user_id,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }
