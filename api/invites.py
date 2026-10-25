"""
Invite API endpoints.

Handles accepting group and admin invites.
"""

import re

from flasgger import swag_from
from flask_jwt_extended import get_jwt_identity, jwt_required

from api import api_bp
from api.utils import api_error, api_response
from models import EmailInvite, GroupsAndUsersAssociation, User, db


@api_bp.route("/invites/<code>/accept", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Invites"],
    "summary": "Accept an invite",
    "description": "Accept a group or admin invite using the invite code sent via email. GROUP-* codes add you as a regular member, ADMIN-* codes add you as a group admin.",
    "parameters": [
        {
            "name": "code",
            "in": "path",
            "type": "string",
            "required": True,
            "description": "Invite code (e.g., GROUP-ABC123 or ADMIN-XYZ789)",
        }
    ],
    "responses": {
        "200": {
            "description": "Invite accepted successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "group_id": {"type": "integer"},
                            "is_admin": {"type": "boolean"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Invalid invite code format"},
        "401": {"description": "Missing or invalid token"},
        "403": {"description": "Invite code was sent to a different user"},
        "404": {"description": "Invalid or expired invite code"},
        "409": {"description": "Already a member of this group"},
    },
})
def api_accept_invite(code):
    """
    Accept a group or admin invite using the invite code.

    The invite code is sent via email and determines the type of invite:
    - GROUP-* : Adds user to a group as a regular member
    - ADMIN-* : Adds user to a group as an admin
    """
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    invite = EmailInvite.query.filter_by(code=code).first()

    if not invite:
        return api_error("Invalid or expired invite code", 404)

    group_id = invite.payload.get("group_id")

    if not group_id:
        return api_error("Invalid invite payload", 400)

    # Handle admin invite
    if re.search(r"\AADMIN-(\d|[A-Z])+\Z", code):
        existing_assoc = GroupsAndUsersAssociation.query.filter_by(
            group_id=group_id, user_id=user.id
        ).first()

        if existing_assoc:
            existing_assoc.group_admin = True
            existing_assoc.save_to_db(db)
        else:
            new_assoc = GroupsAndUsersAssociation(
                group_id=group_id, user_id=user.id, group_admin=True
            )
            new_assoc.save_to_db(db)

        invite.delete_from_db(db)

        return api_response(
            {
                "message": "You are now an admin of the group",
                "group_id": group_id,
                "is_admin": True,
            }
        )

    # Handle group invite
    if re.search(r"\AGROUP-(\d|[A-Z])+\Z", code):
        invite_user_id = invite.payload.get("user_id")

        # If invite was for a specific user, verify it matches
        if invite_user_id:
            if invite_user_id != user.id:
                return api_error("This invite code was sent to a different user", 403)
        else:
            # Invite was for a new user (by email) - verify email matches
            if user.email != invite.invited_email:
                return api_error("This invite code was sent to a different email", 403)

        # Check if already a member
        existing_assoc = GroupsAndUsersAssociation.query.filter_by(
            group_id=group_id, user_id=user.id
        ).first()

        if existing_assoc:
            invite.delete_from_db(db)
            return api_error("You are already a member of this group", 409)

        new_assoc = GroupsAndUsersAssociation(
            group_id=group_id, user_id=user.id, group_admin=False
        )
        new_assoc.save_to_db(db)

        invite.delete_from_db(db)

        return api_response(
            {
                "message": "You have joined the group",
                "group_id": group_id,
                "is_admin": False,
            }
        )

    return api_error("Invalid invite code format", 400)
