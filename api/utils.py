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


BUDGET_CURRENCIES = ("USD", "CAD", "GBP", "EUR", "INR", "AUD")
DEFAULT_BUDGET_CURRENCY = "USD"
# Sanity cap, in minor units (10,000.00 of any currency)
MAX_BUDGET_CENTS = 1_000_000

# Swagger schema for the budget field in request and response bodies
BUDGET_SCHEMA = {
    "type": "object",
    "x-nullable": True,
    "description": "Spending limit per gift, or null for no budget",
    "properties": {
        "amount_cents": {
            "type": "integer",
            "example": 2500,
            "description": "Amount in the currency's minor unit, e.g. cents",
        },
        "currency": {
            "type": "string",
            "enum": list(BUDGET_CURRENCIES),
            "default": DEFAULT_BUDGET_CURRENCY,
        },
    },
}


def parse_budget(budget):
    """
    Validate a budget from a request body.

    Args:
        budget: None to clear the budget, or {"amount_cents": int, "currency": str}
            with currency optional (defaults to USD)

    Returns:
        (amount_cents, currency) tuple, with amount_cents None when clearing

    Raises:
        ValueError: with a message for the client
    """
    if budget is None:
        return None, DEFAULT_BUDGET_CURRENCY

    if not isinstance(budget, dict):
        raise ValueError("'budget' must be an object or null")

    amount = budget.get("amount_cents")
    # bool is a subclass of int, so rule it out explicitly
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise ValueError("'budget.amount_cents' must be a whole number")
    if not 1 <= amount <= MAX_BUDGET_CENTS:
        raise ValueError(
            f"'budget.amount_cents' must be between 1 and {MAX_BUDGET_CENTS}"
        )

    currency = budget.get("currency", DEFAULT_BUDGET_CURRENCY)
    if currency not in BUDGET_CURRENCIES:
        raise ValueError(
            f"'budget.currency' must be one of {', '.join(BUDGET_CURRENCIES)}"
        )

    return amount, currency


def serialize_budget(group):
    """A group's budget as {"amount_cents", "currency"}, or None if it has none."""
    if group.budget_cents is None:
        return None
    return {"amount_cents": group.budget_cents, "currency": group.budget_currency}


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
        "budget": serialize_budget(group),
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
