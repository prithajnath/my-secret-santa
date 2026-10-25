"""
Group map API endpoints: approximate member locations for a group (opt-in).

Members are shown at their nearest major US place (sql/data/us_places.csv) rather than
at their address. This is deterministic on purpose: random jitter that changes per
request can be averaged away to recover the real location.
"""

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required
from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select, true

from api import api_bp
from api.utils import VERIFIED_GEOCODE_STATUSES, api_error, api_response
from models import (
    Group,
    GroupsAndUsersAssociation,
    Place,
    User,
    all_latest_pairs_view,
    db,
)

def _point(lat, lon, precision, city, state):
    if lat is None or lon is None:
        return None
    return {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "precision": precision,
        "city": city,
        "state": state,
    }


@api_bp.route("/groups/<int:group_id>/map", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Groups"],
    "summary": "Get the group map",
    "description": "Members of the group and their approximate locations: each member is placed at the nearest major US city (population >= 50k, or the largest in their state) rather than at their address. Only members who opted in (show_on_map) and have a verified address get a location. The viewer's own giftee is shown at their exact location, since the santa can already see their address.",
    "parameters": [
        {"name": "group_id", "in": "path", "type": "integer", "required": True}
    ],
    "responses": {
        "200": {
            "description": "Group map",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "show_on_map": {"type": "boolean", "description": "Whether the viewer is shown on this group's map"},
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
                                        "is_me": {"type": "boolean"},
                                        "is_my_giftee": {"type": "boolean"},
                                        "location": {
                                            "type": "object",
                                            "description": "null when the member opted out or has no verified address",
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lon": {"type": "number"},
                                                "precision": {"type": "string", "enum": ["approximate", "exact"]},
                                                "city": {"type": "string", "example": "Saint Paul", "description": "approximate: the nearest major city; exact: the city from the address"},
                                                "state": {"type": "string", "example": "MN"},
                                            },
                                        },
                                        "location_unavailable_reason": {
                                            "type": "string",
                                            "description": "Only set for the viewer's own entry: opted_out or no_verified_address",
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
        "403": {"description": "Not a member of this group"},
        "404": {"description": "Group not found"},
    },
})
def api_get_group_map(group_id):
    identity = get_jwt_identity()
    viewer = db.session.get(User, identity)

    if not viewer:
        return api_error("User not found", 404)

    group = db.session.get(Group, group_id)

    if not group:
        return api_error("Group not found", 404)

    viewer_membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=viewer.id
    ).first()

    if not viewer_membership:
        return api_error("You are not a member of this group", 403)

    giftee = all_latest_pairs_view.query.filter_by(
        group_name=group.name, giver_username=viewer.username
    ).first()
    giftee_username = giftee.receiver_username if giftee else None

    point = cast(User.location, Geometry)
    place_point = cast(Place.location, Geometry)
    # Nearest place per member (KNN on the places GiST index)
    nearest_place = (
        select(
            Place.name.label("name"),
            Place.state.label("state"),
            func.ST_Y(place_point).label("lat"),
            func.ST_X(place_point).label("lon"),
        )
        .where(User.location.isnot(None))
        .order_by(Place.location.op("<->")(User.location))
        .limit(1)
        .correlate(User)
        .lateral("nearest_place")
    )
    rows = (
        db.session.query(
            User,
            GroupsAndUsersAssociation.show_on_map,
            func.ST_Y(point),
            func.ST_X(point),
            nearest_place.c.name,
            nearest_place.c.state,
            nearest_place.c.lat,
            nearest_place.c.lon,
        )
        .join(GroupsAndUsersAssociation, GroupsAndUsersAssociation.user_id == User.id)
        .outerjoin(nearest_place, true())
        .filter(GroupsAndUsersAssociation.group_id == group_id)
        .order_by(User.first_name, User.username)
        .all()
    )

    members = []
    for (
        user,
        show_on_map,
        lat,
        lon,
        place_name,
        place_state,
        place_lat,
        place_lon,
    ) in rows:
        is_me = user.id == viewer.id
        is_my_giftee = user.username == giftee_username
        verified = user.geocode_status in VERIFIED_GEOCODE_STATUSES and lat is not None

        location = None
        reason = None
        if not show_on_map:
            reason = "opted_out"
        elif not verified:
            reason = "no_verified_address"
        elif is_my_giftee:
            # The santa already sees this address, so show it as-is
            location = _point(lat, lon, "exact", user.city, user.state)
        else:
            location = _point(place_lat, place_lon, "approximate", place_name, place_state)

        member = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
            "is_me": is_me,
            "is_my_giftee": is_my_giftee,
            "location": location,
        }
        # Why someone else has no pin is their business; only explain it to the viewer
        if is_me:
            member["location_unavailable_reason"] = reason
        members.append(member)

    return api_response(
        {"show_on_map": viewer_membership.show_on_map, "members": members}
    )


@api_bp.route("/groups/<int:group_id>/membership", methods=["PATCH"])
@jwt_required()
@swag_from({
    "tags": ["Groups"],
    "summary": "Update your membership settings",
    "description": "Currently only show_on_map: opt in or out of showing your nearest major city on this group's map.",
    "parameters": [
        {"name": "group_id", "in": "path", "type": "integer", "required": True},
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["show_on_map"],
                "properties": {"show_on_map": {"type": "boolean"}},
            },
        },
    ],
    "responses": {
        "200": {"description": "Membership updated"},
        "400": {"description": "Validation error"},
        "401": {"description": "Missing or invalid token"},
        "404": {"description": "Group not found or not a member"},
    },
})
def api_update_membership(group_id):
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    membership = GroupsAndUsersAssociation.query.filter_by(
        group_id=group_id, user_id=user.id
    ).first()

    if not membership:
        return api_error("You are not a member of this group", 404)

    data = request.get_json(silent=True) or {}

    if not isinstance(data.get("show_on_map"), bool):
        return api_error("show_on_map must be true or false", 400)

    membership.show_on_map = data["show_on_map"]
    membership.save_to_db(db)

    return api_response({"group_id": group_id, "show_on_map": membership.show_on_map})
