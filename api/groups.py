"""
Groups API endpoints.
"""

from datetime import datetime, timedelta

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, func

from api import api_bp
from api.utils import api_error, api_response, serialize_group
from models import (
    EmailInvite,
    Group,
    GroupPairReveals,
    GroupsAndUsersAssociation,
    Pair,
    PairCreationStatus,
    Task,
    User,
    db,
)
from sql import AdvisoryLock

# A create_pairs task older than this is treated as dead, not in progress
DRAW_IN_PROGRESS_WINDOW = timedelta(minutes=30)


@api_bp.route("/groups", methods=["GET"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "List user's groups",
        "description": "Get all groups the authenticated user is a member of",
        "responses": {
            "200": {
                "description": "List of groups",
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer", "example": 1},
                                    "name": {
                                        "type": "string",
                                        "example": "Family Secret Santa",
                                    },
                                    "reveal_latest_pairs": {
                                        "type": "boolean",
                                        "example": False,
                                    },
                                    "member_count": {"type": "integer", "example": 5},
                                    "member_avatars": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "is_admin": {"type": "boolean", "example": True},
                                    "created_at": {
                                        "type": "string",
                                        "format": "date-time",
                                    },
                                    "participating": {
                                        "type": "boolean",
                                        "description": "Whether the current user is in this group's draw",
                                    },
                                    "pairs_drawn_at": {
                                        "type": "string",
                                        "format": "date-time",
                                        "description": "When names were last drawn, or null",
                                    },
                                    "draw_status": {
                                        "type": "string",
                                        "enum": ["none", "in_progress", "done"],
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "401": {"description": "Missing or invalid token"},
        },
    }
)
def api_list_groups():
    """List all groups the current user is a member of."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group_ids = [assoc.group_id for assoc in user.groups]

    # Latest draw per group
    drawn_at = dict(
        db.session.query(Pair.group_id, func.max(Pair.timestamp))
        .filter(Pair.group_id.in_(group_ids))
        .group_by(Pair.group_id)
        .all()
    ) if group_ids else {}

    # Draws queued or running. Ignore stale tasks so a crashed job can't look busy forever
    running_draws = {
        task.payload.get("group_id")
        for task in Task.query.filter(
            Task.name == "create_pairs",
            Task.status.in_(["starting", "processing"]),
            Task.started_at >= datetime.now() - DRAW_IN_PROGRESS_WINDOW,
        )
    }

    groups = []
    for assoc in user.groups:
        group = assoc.group
        if group.id in running_draws:
            draw_status = "in_progress"
        elif drawn_at.get(group.id):
            draw_status = "done"
        else:
            draw_status = "none"
        groups.append(
            {
                "id": group.id,
                "name": group.name,
                "reveal_latest_pairs": group.reveal_latest_pairs,
                "member_count": len(group.users),
                "member_avatars": [u.user.avatar_url for u in group.users][:3],
                "is_admin": assoc.group_admin,
                "created_at": (
                    group.created_at.isoformat() if group.created_at else None
                ),
                "participating": bool(assoc.participating),
                "pairs_drawn_at": (
                    drawn_at[group.id].isoformat() if drawn_at.get(group.id) else None
                ),
                "draw_status": draw_status,
            }
        )

    return api_response(groups)


@api_bp.route("/groups", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Create a new group",
        "description": "Create a new Secret Santa group. The creator becomes the group admin.",
        "parameters": [
            {
                "name": "body",
                "in": "body",
                "required": True,
                "schema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "example": "Office Secret Santa 2024",
                        },
                    },
                },
            }
        ],
        "responses": {
            "201": {
                "description": "Group created successfully",
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "reveal_latest_pairs": {"type": "boolean"},
                                "created_at": {"type": "string", "format": "date-time"},
                                "member_count": {"type": "integer"},
                                "members": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                },
                            },
                        },
                    },
                },
            },
            "400": {"description": "Validation error"},
            "401": {"description": "Missing or invalid token"},
            "409": {"description": "Group name already exists"},
        },
    }
)
def api_create_group():
    """Create a new group."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    data = request.get_json()

    if not data or "name" not in data:
        return api_error("Group name is required", 400)

    group_name = data["name"].strip()

    if not group_name:
        return api_error("Group name cannot be empty", 400)

    # Check if group already exists
    existing_group = Group.query.filter_by(name=group_name).first()
    if existing_group:
        return api_error(f"Group with name '{group_name}' already exists", 409)

    # Create the group
    new_group = Group(name=group_name)
    new_group.save_to_db(db)

    # Add creator as admin
    new_group_assoc = GroupsAndUsersAssociation(
        group=new_group, user=user, group_admin=True
    )
    new_group_assoc.save_to_db(db)

    return api_response(serialize_group(new_group, include_members=True), 201)


@api_bp.route("/groups/<int:group_id>", methods=["GET"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Get group details",
        "description": "Get detailed information about a specific group including all members",
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
                "description": "Group details retrieved successfully",
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "reveal_latest_pairs": {"type": "boolean"},
                                "created_at": {"type": "string", "format": "date-time"},
                                "member_count": {"type": "integer"},
                                "members": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "user_id": {"type": "integer"},
                                            "username": {"type": "string"},
                                            "first_name": {"type": "string"},
                                            "last_name": {"type": "string"},
                                            "avatar_url": {"type": "string"},
                                            "is_admin": {"type": "boolean"},
                                            "participating": {"type": "boolean"},
                                        },
                                    },
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
    }
)
def api_get_group(group_id):
    """Get a specific group's details."""
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

    return api_response(serialize_group(group, include_members=True))


@api_bp.route("/groups/<int:group_id>/membership", methods=["DELETE"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Leave a group",
        "description": "Remove yourself from a group",
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
                "description": "Successfully left the group",
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
            "401": {"description": "Missing or invalid token"},
            "404": {"description": "Group not found or not a member"},
        },
    }
)
def api_leave_group(group_id):
    """Leave a group."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=user.id
    ).first()

    if not membership:
        return api_error("You are not a member of this group", 404)

    membership.delete_from_db(db)

    return api_response({"message": f"Successfully left group '{group.name}'"})


@api_bp.route("/groups/<int:group_id>/members", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Invite a user to the group",
        "description": "Send an email invitation to join the group. If the user doesn't have an account, they'll be invited to sign up.",
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
                    "required": ["email"],
                    "properties": {
                        "email": {
                            "type": "string",
                            "format": "email",
                            "example": "friend@example.com",
                        },
                    },
                },
            },
        ],
        "responses": {
            "201": {
                "description": "Invitation sent successfully",
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
            "401": {"description": "Missing or invalid token"},
            "403": {"description": "Not a member of this group"},
            "404": {"description": "Group not found"},
        },
    }
)
def api_invite_member(group_id):
    """Invite a user to join a group."""
    from app import celery

    identity = get_jwt_identity()
    current_user = db.session.get(User, identity)

    if not current_user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if current user is a member (and optionally admin)
    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=current_user.id
    ).first()

    if not membership:
        return api_error("You are not a member of this group", 403)

    data = request.get_json()

    if not data or "email" not in data:
        return api_error("Email is required", 400)

    email = data["email"].strip().lower()

    # Check if user with this email already exists
    invited_user = User.query.filter_by(email=email).first()

    # Create invite
    new_invite = EmailInvite(
        timestamp=datetime.now(),
        invited_email=email,
        code=EmailInvite.generate_code("group"),
        payload=(
            {"group_id": group.id, "user_id": invited_user.id}
            if invited_user
            else {"group_id": group.id}
        ),
    )
    new_invite.save_to_db(db)

    # Create task and send email
    if invited_user:
        # Existing user - invite to group
        task = Task(
            name="invite_user_to_group",
            started_at=datetime.now(),
            status="starting",
            payload={
                "to_email": email,
                "admin_first_name": current_user.first_name,
                "invite_code": new_invite.code,
                "group_name": group.name,
            },
        )
        task.save_to_db(db)

        celery.send_task(
            "user.invite_user_to_group",
            (email, current_user.first_name, group.name),
        )

        return api_response(
            {"message": f"Invitation sent to {email} to join the group"}, 201
        )
    else:
        # New user - invite to sign up
        task = Task(
            name="invite_user_to_sign_up",
            started_at=datetime.now(),
            status="starting",
            payload={
                "to_email": email,
                "admin_first_name": current_user.first_name,
                "invite_code": new_invite.code,
                "group_name": group.name,
            },
        )
        task.save_to_db(db)

        celery.send_task(
            "user.invite_user_to_sign_up",
            (email, current_user.first_name, group.name),
        )

        return api_response(
            {"message": f"Invitation sent to {email} to create an account and join"},
            201,
        )


@api_bp.route("/groups/<int:group_id>/members/<int:user_id>", methods=["DELETE"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Kick a member from the group",
        "description": "Remove a member from the group. Only group admins can perform this action.",
        "parameters": [
            {
                "name": "group_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "Group ID",
            },
            {
                "name": "user_id",
                "in": "path",
                "type": "integer",
                "required": True,
                "description": "User ID to remove",
            },
        ],
        "responses": {
            "200": {
                "description": "Member removed successfully",
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
            "400": {"description": "Cannot kick yourself"},
            "401": {"description": "Missing or invalid token"},
            "403": {"description": "Only admins can remove members"},
            "404": {"description": "Group or user not found"},
        },
    }
)
def api_kick_member(group_id, user_id):
    """Kick a member from a group (admin only)."""
    identity = get_jwt_identity()
    current_user = db.session.get(User, identity)

    if not current_user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if current user is admin
    if not group.is_admin(current_user):
        return api_error("Only group admins can remove members", 403)

    # Can't kick yourself
    if user_id == current_user.id:
        return api_error("You cannot kick yourself from the group", 400)

    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=user_id
    ).first()

    if not membership:
        return api_error("User is not a member of this group", 404)

    membership.delete_from_db(db)

    return api_response({"message": "Member removed from group"})


@api_bp.route("/groups/<int:group_id>/pairs", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Create secret santa pairs",
        "description": "Generate secret santa pairs for all group members. Only group admins can perform this action. There is a 1-day cooldown between pair generations.",
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
            "202": {
                "description": "Pair creation initiated",
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
            "401": {"description": "Missing or invalid token"},
            "403": {"description": "Only admins can create pairs"},
            "404": {"description": "Group not found"},
            "409": {"description": "Pair creation already in progress"},
            "429": {"description": "Group is in cooldown period"},
        },
    }
)
def api_create_pairs(group_id):
    """Create secret santa pairs for a group (admin only)."""
    from app import celery

    identity = get_jwt_identity()
    current_user = db.session.get(User, identity)

    if not current_user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if current user is admin
    if not group.is_admin(current_user):
        return api_error("Only group admins can create pairs", 403)

    # Check for ongoing pair creation
    currently_running = PairCreationStatus.query.filter_by(
        group_id=group.id, status="creating"
    ).first()

    if currently_running:
        return api_error("Pair creation is already in progress", 409)

    # Check cooldown
    pair_latest_timestamp = Pair.query.with_entities(
        func.max(Pair.timestamp)
    ).filter_by(group_id=group_id).first()[0] or datetime(1970, 1, 1)

    delta = datetime.now() - pair_latest_timestamp
    if delta.days < 1:
        return api_error(
            "This group is in cooldown. Pairs were created recently. Try again later.",
            429,
        )

    # Create pairs with advisory lock
    with AdvisoryLock(engine=db.engine, lock_key=group.name).grab_lock() as locked:
        lock, session = locked
        if lock:
            creation_task = Task(
                started_at=datetime.now(),
                name="create_pairs",
                payload={
                    "group_id": group.id,
                    "initiator_id": current_user.id,
                },
                status="starting",
            )
            session.add(creation_task)
        else:
            return api_error("Too many concurrent pair creation attempts", 429)

    # Queue the celery task
    celery.send_task("pair.create_pairs", (group_id,))

    return api_response(
        {
            "message": "Pair creation has been initiated. You will be notified when complete."
        },
        202,
    )


@api_bp.route("/groups/<int:group_id>/reveal", methods=["POST"])
@jwt_required()
@swag_from(
    {
        "tags": ["Groups"],
        "summary": "Toggle pair reveal status",
        "description": "Enable or disable revealing of secret santa identities. Only group admins can perform this action.",
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
                    "required": ["reveal"],
                    "properties": {
                        "reveal": {
                            "type": "boolean",
                            "example": True,
                            "description": "Whether to reveal pairs",
                        },
                    },
                },
            },
        ],
        "responses": {
            "200": {
                "description": "Reveal status updated",
                "schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {
                            "type": "object",
                            "properties": {
                                "reveal_latest_pairs": {"type": "boolean"},
                                "message": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "400": {"description": "Missing reveal field"},
            "401": {"description": "Missing or invalid token"},
            "403": {"description": "Only admins can toggle reveal status"},
            "404": {"description": "Group not found"},
            "429": {"description": "Too many concurrent attempts"},
        },
    }
)
def api_toggle_reveal(group_id):
    """Toggle reveal status of secret santa pairs (admin only)."""
    identity = get_jwt_identity()
    current_user = db.session.get(User, identity)

    if not current_user:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    # Check if current user is admin
    if not group.is_admin(current_user):
        return api_error("Only group admins can toggle reveal status", 403)

    data = request.get_json()

    if data is None or "reveal" not in data:
        return api_error("'reveal' boolean field is required", 400)

    reveal = bool(data["reveal"])

    with AdvisoryLock(engine=db.engine, lock_key=group.name).grab_lock() as locked:
        lock, session = locked
        if lock:
            group_in_session = session.query(Group).filter_by(id=group_id).first()
            group_in_session.reveal_latest_pairs = reveal

            group_reveal_history = GroupPairReveals(
                group_id=group_id, user_id=current_user.id, timestamp=datetime.now()
            )
            session.add(group_in_session)
            session.add(group_reveal_history)
        else:
            return api_error("Too many concurrent attempts", 429)

    return api_response(
        {
            "reveal_latest_pairs": reveal,
            "message": f"Pairs are now {'revealed' if reveal else 'hidden'}",
        }
    )
