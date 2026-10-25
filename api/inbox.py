"""
Unread message counts for the dashboard, and read tracking for chats.

Opening a chat (GET of its messages) marks it read up to the newest message returned.
"""

from flasgger import swag_from
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, func, or_
from sqlalchemy.dialects.postgresql import insert

from api import api_bp
from api.utils import api_error, api_response
from models import (
    GroupMessage,
    GroupMessageRead,
    GroupsAndUsersAssociation,
    Message,
    PairMessageRead,
    User,
    all_latest_pairs_view,
    db,
)


def _mark_read(model, key_column, user_id, key, latest_message_at):
    """Move a user's read marker forward to latest_message_at (never backwards)."""
    if latest_message_at is None:
        return
    statement = insert(model).values(
        user_id=user_id, **{key_column: key}, last_read_at=latest_message_at
    )
    statement = statement.on_conflict_do_update(
        index_elements=["user_id", key_column],
        set_={"last_read_at": statement.excluded.last_read_at},
        where=model.last_read_at < statement.excluded.last_read_at,
    )
    db.session.execute(statement)
    db.session.commit()


def mark_group_read(user_id, group_id, latest_message_at):
    _mark_read(GroupMessageRead, "group_id", user_id, group_id, latest_message_at)


def mark_pair_read(user_id, channel_id, latest_message_at):
    _mark_read(PairMessageRead, "channel_id", user_id, channel_id, latest_message_at)


def _iso(value):
    return value.isoformat() if value else None


@api_bp.route("/me/inbox", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Messages"],
    "summary": "Unread message counts",
    "description": "Unread counts and latest message time for each of the current user's group chats and santa/santee channels. A conversation is read up to the newest message returned the last time the user fetched it.",
    "responses": {
        "200": {
            "description": "Inbox summary",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "groups": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "integer"},
                                        "unread": {"type": "integer"},
                                        "last_message_at": {"type": "string", "format": "date-time"},
                                    },
                                },
                            },
                            "pairs": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "channel_id": {"type": "string", "format": "uuid"},
                                        "unread": {"type": "integer"},
                                        "last_message_at": {"type": "string", "format": "date-time"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "401": {"description": "Missing or invalid token"},
    },
})
def api_get_inbox():
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group_ids = [
        group_id
        for (group_id,) in db.session.query(GroupsAndUsersAssociation.group_id).filter_by(
            user_id=user.id
        )
    ]

    # Group chats: one grouped query over the user's groups
    group_rows = (
        db.session.query(
            GroupMessage.group_id,
            func.count(GroupMessage.id).filter(
                and_(
                    GroupMessage.sender_id != user.id,
                    or_(
                        GroupMessageRead.last_read_at.is_(None),
                        GroupMessage.created_at > GroupMessageRead.last_read_at,
                    ),
                )
            ),
            func.max(GroupMessage.created_at),
        )
        .outerjoin(
            GroupMessageRead,
            and_(
                GroupMessageRead.group_id == GroupMessage.group_id,
                GroupMessageRead.user_id == user.id,
            ),
        )
        .filter(GroupMessage.group_id.in_(group_ids))
        .group_by(GroupMessage.group_id)
        .all()
        if group_ids
        else []
    )
    group_stats = {group_id: (unread, last) for group_id, unread, last in group_rows}

    # Santa/santee channels from the latest draws the user is part of
    channel_ids = [
        str(row.channel_id)
        for row in all_latest_pairs_view.query.filter(
            or_(
                all_latest_pairs_view._view.giver_username == user.username,
                all_latest_pairs_view._view.receiver_username == user.username,
            )
        )
    ]
    pair_rows = (
        db.session.query(
            Message.pair_channel_id,
            func.count(Message.id).filter(
                and_(
                    Message.receiver_id == user.id,
                    or_(
                        PairMessageRead.last_read_at.is_(None),
                        Message.created_at > PairMessageRead.last_read_at,
                    ),
                )
            ),
            func.max(Message.created_at),
        )
        .outerjoin(
            PairMessageRead,
            and_(
                PairMessageRead.channel_id == Message.pair_channel_id,
                PairMessageRead.user_id == user.id,
            ),
        )
        .filter(Message.pair_channel_id.in_(channel_ids))
        .group_by(Message.pair_channel_id)
        .all()
        if channel_ids
        else []
    )
    pair_stats = {str(channel_id): (unread, last) for channel_id, unread, last in pair_rows}

    return api_response(
        {
            "groups": [
                {
                    "group_id": group_id,
                    "unread": group_stats.get(group_id, (0, None))[0],
                    "last_message_at": _iso(group_stats.get(group_id, (0, None))[1]),
                }
                for group_id in group_ids
            ],
            "pairs": [
                {
                    "channel_id": channel_id,
                    "unread": pair_stats.get(channel_id, (0, None))[0],
                    "last_message_at": _iso(pair_stats.get(channel_id, (0, None))[1]),
                }
                for channel_id in channel_ids
            ],
        }
    )
