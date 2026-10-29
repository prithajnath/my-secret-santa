"""
Santa/Santee API endpoints.

Handles viewing secret santa relationships and revealing identities.
"""

from random import choices

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from api import api_bp
from api.utils import (
    BUDGET_SCHEMA,
    api_error,
    api_response,
    serialize_budget,
)
from models import Group, User, all_latest_pairs_view, db


@api_bp.route("/santa", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Santa"],
    "summary": "Get santas and santees",
    "description": "Get the current user's secret santa relationships across all groups",
    "responses": {
        "200": {
            "description": "Santa relationships retrieved",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "santas": {
                                "type": "array",
                                "description": "Groups where someone is your secret santa",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "integer"},
                                        "group_name": {"type": "string"},
                                        "channel_id": {"type": "string", "format": "uuid"},
                                        "reveal_enabled": {"type": "boolean"},
                                        "budget": BUDGET_SCHEMA,
                                    },
                                },
                            },
                            "santees": {
                                "type": "array",
                                "description": "People you are the secret santa for",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "integer"},
                                        "group_name": {"type": "string"},
                                        "channel_id": {"type": "string", "format": "uuid"},
                                        "budget": BUDGET_SCHEMA,
                                        "santee": {
                                            "type": "object",
                                            "properties": {
                                                "username": {"type": "string"},
                                                "first_name": {"type": "string"},
                                                "last_name": {"type": "string"},
                                                "avatar_url": {"type": "string"},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
        "404": {"description": "User not found"},
    },
})
def api_get_santas_and_santees():
    """
    Get the current user's santa and santee relationships.

    Returns:
        - santas: People who are buying gifts FOR the current user
        - santees: People the current user is buying gifts for
    """
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    # Get all pairs where user is either giver or receiver
    all_pairs = all_latest_pairs_view.query.filter(
        or_(
            all_latest_pairs_view._view.giver_username == user.username,
            all_latest_pairs_view._view.receiver_username == user.username,
        )
    ).all()

    # Santas: pairs where user is the receiver (someone is their secret santa)
    santas = []
    for pair in all_pairs:
        if pair.receiver_username == user.username:
            group = Group.query.filter_by(name=pair.group_name).first()
            santas.append(
                {
                    "group_id": group.id if group else None,
                    "group_name": pair.group_name,
                    "channel_id": str(pair.channel_id),
                    "reveal_enabled": group.reveal_latest_pairs if group else False,
                    "budget": serialize_budget(group) if group else None,
                }
            )

    # Santees: pairs where user is the giver (they are someone's secret santa)
    santees = []
    for pair in all_pairs:
        if pair.giver_username == user.username:
            santee_user = User.query.filter_by(username=pair.receiver_username).first()
            group = Group.query.filter_by(name=pair.group_name).first()
            santees.append(
                {
                    "group_id": group.id if group else None,
                    "group_name": pair.group_name,
                    "channel_id": str(pair.channel_id),
                    "budget": serialize_budget(group) if group else None,
                    "santee": {
                        "username": pair.receiver_username,
                        "first_name": santee_user.first_name if santee_user else None,
                        "last_name": santee_user.last_name if santee_user else None,
                        "avatar_url": santee_user.avatar_url if santee_user else None,
                    },
                }
            )

    return api_response(
        {
            "santas": santas,
            "santees": santees,
        }
    )


@api_bp.route("/santa/reveal", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Santa"],
    "summary": "Reveal secret santa",
    "description": "Reveal who your secret santa is for a specific group. Includes decoy names for a fun reveal experience. Only works if the group admin has enabled reveals.",
    "parameters": [
        {
            "name": "group_name",
            "in": "query",
            "type": "string",
            "required": True,
            "description": "Name of the group to reveal secret santa for",
        }
    ],
    "responses": {
        "200": {
            "description": "Secret santa revealed",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "secret_santa_username": {"type": "string", "example": "johndoe"},
                            "secret_santa": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "avatar_url": {"type": "string"},
                                },
                            },
                            "decoy_usernames": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Random member names for reveal animation",
                            },
                        },
                    },
                },
            },
        },
        "400": {"description": "Missing group_name parameter"},
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "Reveal is not enabled for this group"},
        "404": {"description": "Group not found or no secret santa in this group"},
    },
})
def api_reveal_secret_santa():
    """
    Reveal who the current user's secret santa is for a specific group.

    Returns the santa's username along with decoy usernames for a fun reveal experience.

    Query parameters:
        - group_name: The name of the group to reveal for
    """
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group_name = request.args.get("group_name")

    if not group_name:
        return api_error("'group_name' query parameter is required", 400)

    group = Group.query.filter_by(name=group_name).first()

    if not group:
        return api_error("Group not found", 404)

    # Check if reveal is enabled for this group
    if not group.reveal_latest_pairs:
        return api_error("Secret santa reveal is not enabled for this group", 403)

    # Get the secret santa pair
    secret_santa_pair = all_latest_pairs_view.query.filter_by(
        group_name=group_name, receiver_username=user.username
    ).first()

    if not secret_santa_pair:
        return api_error("You don't have a secret santa in this group", 404)

    # Get random decoy usernames from the group, excluding the current user
    group_members = [
        assoc.user.username
        for assoc in group.users
        if assoc.user.username != user.username
    ]
    decoys = choices(group_members, k=min(10, len(group_members)))

    santa_user = User.query.filter_by(username=secret_santa_pair.giver_username).first()

    return api_response(
        {
            "secret_santa_username": secret_santa_pair.giver_username,
            "secret_santa": {
                "username": secret_santa_pair.giver_username,
                "first_name": santa_user.first_name if santa_user else None,
                "last_name": santa_user.last_name if santa_user else None,
                "avatar_url": santa_user.avatar_url if santa_user else None,
            },
            "decoy_usernames": decoys,
        }
    )
