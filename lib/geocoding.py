"""
Forward geocoding of free-text addresses: US Census first (free, US-only), then Geoapify
(worldwide) for addresses Census can't place and to tell US from non-US addresses.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

import requests

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
GEOAPIFY_SEARCH_URL = "https://api.geoapify.com/v1/geocode/search"
# Below this Geoapify confidence a result is treated as no match
GEOAPIFY_MIN_CONFIDENCE = 0.5


@dataclass
class GeocodeResult:
    # census, geoapify (a US match) or non_us
    source: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country_code: Optional[str] = None


def normalize_address(address):
    """Collapse a multi-line address (old textarea input) into one comma-separated line."""
    lines = [line.strip(" ,") for line in re.split(r"[\r\n]+", address)]
    return re.sub(r"\s+", " ", ", ".join(line for line in lines if line)).strip()


def census_geocode(address):
    """US Census one-line geocoder. Returns a GeocodeResult or None if no match."""
    response = requests.get(
        CENSUS_URL,
        params={"address": address, "benchmark": "Public_AR_Current", "format": "json"},
        timeout=30,
    )
    response.raise_for_status()
    matches = response.json()["result"]["addressMatches"]
    if not matches:
        return None

    match = matches[0]
    components = match["addressComponents"]
    return GeocodeResult(
        source="census",
        lat=match["coordinates"]["y"],
        lon=match["coordinates"]["x"],
        city=components["city"].title(),
        state=components["state"],
        zip=components["zip"],
        country_code="us",
    )


def geoapify_geocode(address):
    """
    Geoapify forward geocoding, worldwide. Returns a GeocodeResult (source geoapify for
    US matches, non_us otherwise) or None if there's no confident match or no API key.
    """
    api_key = os.getenv("GEOAPIFY_API_KEY")
    if not api_key:
        return None

    response = requests.get(
        GEOAPIFY_SEARCH_URL,
        params={"text": address, "format": "json", "limit": 1, "apiKey": api_key},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        return None

    result = results[0]
    if (result.get("rank") or {}).get("confidence", 0) < GEOAPIFY_MIN_CONFIDENCE:
        return None

    country_code = (result.get("country_code") or "").lower()
    if country_code != "us":
        # Outside the US: only the country matters, coordinates aren't kept
        return GeocodeResult(source="non_us", country_code=country_code or None)

    return GeocodeResult(
        source="geoapify",
        lat=result.get("lat"),
        lon=result.get("lon"),
        city=result.get("city"),
        state=result.get("state_code"),
        zip=result.get("postcode"),
        country_code="us",
    )


def geocode_address(address):
    """Census first, Geoapify as fallback. Returns a GeocodeResult or None."""
    normalized = normalize_address(address)
    if not normalized:
        return None
    return census_geocode(normalized) or geoapify_geocode(normalized)
