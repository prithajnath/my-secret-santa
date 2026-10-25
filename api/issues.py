"""
Issue reporting API endpoints.
"""

from flasgger import swag_from
from flask import request
from flask_jwt_extended import get_jwt_identity, jwt_required

from api import api_bp
from api.utils import api_error, api_response
from models import Issue, User, db


@api_bp.route("/issues", methods=["POST"])
@jwt_required()
@swag_from({
    "tags": ["Issues"],
    "summary": "Report an issue",
    "description": "Submit a bug report or feedback about the application",
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "required": ["title", "description"],
                "properties": {
                    "title": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 150,
                        "example": "Cannot send messages to my santee",
                    },
                    "description": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 500,
                        "example": "When I try to send a message, I get an error saying 'Something went wrong'. This happens every time I click send.",
                    },
                },
            },
        }
    ],
    "responses": {
        "201": {
            "description": "Issue reported successfully",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "issue_id": {"type": "integer"},
                        },
                    },
                },
            },
        },
        "400": {"description": "Validation error"},
        "401": {"description": "Missing or invalid token"},
    },
})
def api_report_issue():
    """Report a bug or issue."""
    identity = get_jwt_identity()
    user = db.session.get(User, identity)

    if not user:
        return api_error("User not found", 404)

    data = request.get_json()

    if not data:
        return api_error("Request body is required", 400)

    if "title" not in data:
        return api_error("Issue title is required", 400)

    if "description" not in data:
        return api_error("Issue description is required", 400)

    title = data["title"].strip()
    description = data["description"].strip()

    if len(title) < 10 or len(title) > 150:
        return api_error("Title must be between 10 and 150 characters", 400)

    if len(description) < 10 or len(description) > 500:
        return api_error("Description must be between 10 and 500 characters", 400)

    new_issue = Issue(
        user_id=user.id,
        title=title,
        description=description,
    )
    new_issue.save_to_db(db)

    return api_response(
        {
            "message": "Thank you for your feedback! We'll get back to you soon.",
            "issue_id": new_issue.id,
        },
        201,
    )
