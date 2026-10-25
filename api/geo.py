"""
Geocoding API endpoints (US-only address autocomplete).
"""

import json
import os

import redis
import requests
from flasgger import swag_from
from flask import current_app, request
from flask_jwt_extended import jwt_required

from api import api_bp
from api.utils import api_error, api_response

GEOAPIFY_AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
# Geoapify autocomplete often takes several seconds, so allow for it and cache answers
GEOAPIFY_TIMEOUT_SECONDS = 8
AUTOCOMPLETE_CACHE_TTL_SECONDS = 24 * 60 * 60

_cache = None


def get_cache():
    """Redis client for caching suggestions (the Celery broker); None if unavailable."""
    global _cache
    if _cache is None and os.getenv("CELERY_BROKER_URL"):
        _cache = redis.Redis.from_url(
            os.getenv("CELERY_BROKER_URL"), socket_timeout=0.5, socket_connect_timeout=0.5
        )
    return _cache


def cache_get(key):
    try:
        cached = get_cache() and get_cache().get(key)
        return json.loads(cached) if cached else None
    except redis.RedisError:
        return None


def cache_set(key, value):
    try:
        if get_cache():
            get_cache().setex(key, AUTOCOMPLETE_CACHE_TTL_SECONDS, json.dumps(value))
    except redis.RedisError:
        pass


def serialize_suggestion(result):
    """Map a Geoapify autocomplete result to our address shape."""
    street = " ".join(
        part for part in (result.get("housenumber"), result.get("street")) if part
    )
    return {
        "place_id": result.get("place_id"),
        "label": result.get("formatted"),
        "address_line1": street or result.get("address_line1"),
        "city": result.get("city"),
        "state": result.get("state_code"),
        "zip": result.get("postcode"),
        "lat": result.get("lat"),
        "lon": result.get("lon"),
        "result_type": result.get("result_type"),
    }


@api_bp.route("/geo/autocomplete", methods=["GET"])
@jwt_required()
@swag_from({
    "tags": ["Geo"],
    "summary": "Autocomplete a US address",
    "description": "Returns up to 5 US address suggestions for the given partial address. Pass a suggestion's fields back to PUT /users/me as `address_components`.",
    "parameters": [
        {
            "name": "q",
            "in": "query",
            "type": "string",
            "required": True,
            "description": "Partial address (at least 3 characters)",
        }
    ],
    "responses": {
        "200": {
            "description": "Address suggestions",
            "schema": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "place_id": {"type": "string"},
                                "label": {"type": "string", "example": "1554 Midway Parkway, St Paul, MN 55108"},
                                "address_line1": {"type": "string", "example": "1554 Midway Parkway"},
                                "city": {"type": "string"},
                                "state": {"type": "string", "example": "MN"},
                                "zip": {"type": "string", "example": "55108"},
                                "lat": {"type": "number"},
                                "lon": {"type": "number"},
                                "result_type": {"type": "string", "example": "building"},
                            },
                        },
                    },
                },
            },
        },
        "400": {"description": "Query too short"},
        "401": {"description": "Missing or invalid token"},
        "502": {"description": "Geocoding provider error"},
        "503": {"description": "Geocoding is not configured"},
    },
})
def api_geo_autocomplete():
    """Proxy US address autocomplete to Geoapify, keeping the API key server-side."""
    query = (request.args.get("q") or "").strip()[:200]

    if len(query) < 3:
        return api_error("Query must be at least 3 characters", 400)

    cache_key = "geo:autocomplete:" + " ".join(query.lower().split())
    cached = cache_get(cache_key)
    if cached is not None:
        return api_response(cached)

    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        return api_error("Address autocomplete is not configured", 503)

    try:
        response = requests.get(
            GEOAPIFY_AUTOCOMPLETE_URL,
            params={
                "text": query,
                "filter": "countrycode:us",
                "lang": "en",
                "limit": 5,
                "format": "json",
                "apiKey": api_key,
            },
            timeout=GEOAPIFY_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        current_app.logger.warning(f"Geoapify autocomplete request failed: {e}")
        return api_error("Address lookup failed, please try again", 502)

    if response.status_code != 200:
        current_app.logger.warning(
            f"Geoapify autocomplete returned HTTP {response.status_code}: {response.text[:200]}"
        )
        return api_error("Address lookup failed, please try again", 502)

    suggestions = [
        serialize_suggestion(result) for result in response.json().get("results", [])
    ]
    cache_set(cache_key, suggestions)

    return api_response(suggestions)
