"""
REST API Blueprint for My Secret Santa

This module provides a RESTful API layer for the Secret Santa application,
enabling modern frontend frameworks (React, Next.js, etc.) to interact with
the backend using JWT authentication.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Import routes to register them with the blueprint
from api import auth, users, groups, messages, santa, invites, issues
