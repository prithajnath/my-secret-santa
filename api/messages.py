"""
Messaging API endpoints.

Handles group chat messages and one-on-one santa/santee messages.
"""

from datetime import datetime

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from api import api_bp
from api.utils import api_error, api_response, serialize_group_message, serialize_message
from models import (
    Group,
    GroupMessage,
    GroupsAndUsersAssociation,
    Message,
    Pair,
    Task,
    User,
    all_latest_pairs_view,
    db,
)


@api_bp.route("/groups/<int:group_id>/messages", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Messages"],
    "summary": "Get group chat messages",
    "description": "Retrieve all messages in a group's chat",
    "parameters": [
        {
            "name": "group_id",
            "in": "path",
            "type": "integer",
            "required": True,
            "description": "Group ID",
        }
    ],
    "responses": {
        "200": {
            "description": "List of group messages",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "text": {"type": "string"},
                                "sender": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "integer"},
                                        "username": {"type": "string"},
                                        "first_name": {"type": "string"},
                                        "avatar_url": {"type": "string"},
                                    },
                                },
                                "is_own_message": {"type": "boolean"},
                                "created_at": {"type": "string", "format": "date-time"},
                            },
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "Not a member of this group"},
        "404": {"description": "Group not found"},
    },
})
def api_get_group_messages(group_id):
    """Get all messages in a group chat."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if user is a member
    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=user.id
    ).first()

    if not membership:
        return api_error("You are not a member of this group", 403)

    messages = (
        GroupMessage.query.filter_by(group_id=group_id)
        .order_by(GroupMessage.created_at)
        .all()
    )

    return api_response(
        [serialize_group_message(msg, user.id) for msg in messages]
    )


@api_bp.route("/groups/<int:group_id>/messages", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Messages"],
    "summary": "Send a group chat message",
    "description": "Send a message to a group's chat. Email notifications are rate-limited to every 15 minutes.",
    "parameters": [
        {
            "name": "group_id",
            "in": "path",
            "type": "integer",
            "required": True,
            "description": "Group ID",
        },
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string", "example": "Happy holidays everyone!"},
                },
            },
        },
    ],
    "responses": {
        "201": {
            "description": "Message sent successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "text": {"type": "string"},
                            "sender": {"type": "object"},
                            "is_own_message": {"type": "boolean", "example": True},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Message is required or empty"},
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "Not a member of this group"},
        "404": {"description": "Group not found"},
    },
})
def api_send_group_message(group_id):
    """Send a message to a group chat."""
    from app import celery

    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if user is a member
    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=user.id
    ).first()

    if not membership:
        return api_error("You are not a member of this group", 403)

    data = request.get_json()

    if not data or "message" not in data:
        return api_error("Message text is required", 400)

    message_text = data["message"]

    if not message_text.strip():
        return api_error("Message cannot be empty", 400)

    # Get the last message for rate limiting notifications
    last_message = (
        GroupMessage.query.filter_by(group_id=group_id)
        .order_by(GroupMessage.created_at.desc())
        .limit(1)
        .first()
    )

    # Create the new message
    new_message = GroupMessage(
        group_id=group_id,
        sender_id=user.id,
        text=message_text,
        created_at=datetime.now(),
    )
    new_message.save_to_db(db)

    # Rate limit notifications (15 minutes between notifications)
    if last_message:
        delta = new_message.created_at - last_message.created_at
    else:
        delta = new_message.created_at - datetime(1970, 1, 1)

    if delta.seconds + delta.days * 86400 >= 900:  # 15 minutes
        task = Task(
            name="send_group_chat_notifications",
            started_at=datetime.now(),
            status="starting",
            payload={
                "sender_username": user.username,
                "text": message_text,
                "group_id": group_id,
            },
        )
        task.save_to_db(db)

        celery.send_task(
            "user.send_group_chat_notifications",
            (user.username, message_text, group_id),
        )

    return api_response(serialize_group_message(new_message, user.id), 201)


@api_bp.route("/pairs/<channel_id>/messages", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Messages"],
    "summary": "Get pair messages",
    "description": "Retrieve all messages in a santa/santee pair channel",
    "parameters": [
        {
            "name": "channel_id",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Pair channel UUID",
        }
    ],
    "responses": {
        "200": {
            "description": "List of pair messages",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "text": {"type": "string"},
                                "direction": {"type": "string", "enum": ["sent", "received"]},
                                "created_at": {"type": "string", "format": "date-time"},
                            },
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "You are not part of this pair"},
        "404": {"description": "Pair channel not found"},
    },
})
def api_get_pair_messages(channel_id):
    """Get messages for a santa/santee pair channel."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    # Verify user is part of this pair
    pair = all_latest_pairs_view.query.filter_by(channel_id=channel_id).first()

    if not pair:
        return api_error("Pair channel not found", 404)

    # User must be either giver or receiver
    if pair.giver_username != user.username and pair.receiver_username != user.username:
        return api_error("You are not part of this pair", 403)

    messages = (
        Message.query.filter_by(pair_channel_id=channel_id)
        .order_by(Message.created_at)
        .all()
    )

    return api_response([serialize_message(msg, user.id) for msg in messages])


@api_bp.route("/pairs/<channel_id>/messages", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Messages"],
    "summary": "Send a pair message",
    "description": "Send a message to your secret santa or santee. Messages from santa to santee are anonymous until reveal is enabled.",
    "parameters": [
        {
            "name": "channel_id",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Pair channel UUID",
        },
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string", "example": "I got you something special!"},
                },
            },
        },
    ],
    "responses": {
        "201": {
            "description": "Message sent successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "text": {"type": "string"},
                            "direction": {"type": "string", "example": "sent"},
                            "created_at": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Message is required or empty"},
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "You are not part of this pair"},
        "404": {"description": "Pair channel not found"},
    },
})
def api_send_pair_message(channel_id):
    """Send a message in a santa/santee pair channel."""
    from app import celery

    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    # Verify user is part of this pair
    pair = all_latest_pairs_view.query.filter_by(channel_id=channel_id).first()

    if not pair:
        return api_error("Pair channel not found", 404)

    # User must be either giver or receiver
    if pair.giver_username != user.username and pair.receiver_username != user.username:
        return api_error("You are not part of this pair", 403)

    data = request.get_json()

    if not data or "message" not in data:
        return api_error("Message text is required", 400)

    message_text = data["message"]

    if not message_text.strip():
        return api_error("Message cannot be empty", 400)

    # Determine receiver
    is_giver = pair.giver_username == user.username

    if is_giver:
        receiver = User.query.filter_by(username=pair.receiver_username).first()
        # Santa sending to santee - anonymous
        is_santa_message = True
    else:
        receiver = User.query.filter_by(username=pair.giver_username).first()
        # Santee sending to santa - not anonymous
        is_santa_message = False

    # Create the message
    new_message = Message(
        sender_id=user.id,
        receiver_id=receiver.id,
        pair_channel_id=channel_id,
        text=message_text,
        created_at=datetime.now(),
    )
    new_message.save_to_db(db)

    # Create notification task
    task = Task(
        name="send_message_notification",
        started_at=datetime.now(),
        status="starting",
        payload={
            "sender_id": user.id,
            "receiver_id": receiver.id,
            "channel_id": channel_id,
            "text": message_text,
        },
    )
    task.save_to_db(db)

    celery.send_task(
        "user.send_message_notification",
        (user.id, receiver.id, channel_id, message_text, is_santa_message),
    )

    return api_response(serialize_message(new_message, user.id), 201)
