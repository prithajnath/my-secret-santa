import json
import logging
import requests
import os

from .base import OAuthHandler, OAuthUser
import urllib.parse as urlparse
from urllib.parse import urlencode

SITE_DOMAIN = "mysecretsanta.io"

ORIGIN = (
    f"https://app.{SITE_DOMAIN}"
    if os.getenv("ENV") == "production"
    else f"https://dev.{SITE_DOMAIN}:9100"
)
REDIRECT_PATH = "google_oauth"

logger = logging.getLogger(__name__)


class Google(OAuthHandler):
    def __init__(self, client_id: str, client_secret: str):
        super().__init__(
            "Google",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            client_id,
            client_secret,
        )

    @property
    def oauth_url(self):
        return self._oauth_url(
            params={
                "redirect_uri": f"{ORIGIN}/{REDIRECT_PATH}",
                "client_id": self.client_id,
                "access_type": "offline",
                "response_type": "code",
                "prompt": "consent",
                "scope": " ".join(
                    [
                        "https://www.googleapis.com/auth/userinfo.profile",
                        "https://www.googleapis.com/auth/userinfo.email",
                    ]
                ),
            }
        )

    def user_data(self, code: str) -> OAuthUser:
        _resp = requests.post(
            self.access_token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": f"{ORIGIN}/{REDIRECT_PATH}",
                "grant_type": "authorization_code",
            },
        )

        data = json.loads(_resp.content)
        logger.info(data)
        access_token, id_token = data["access_token"], data["id_token"]

        resp = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            params={
                "alt": "json",
                "access_token": access_token,
            },
            headers={"Authorization": f"Bearer {id_token}"},
        )

        user = json.loads(resp.content)

        return {
            "id": user["id"],
            "first_name": user["given_name"],
            "last_name": user["family_name"],
            "email": user["email"],
            "avatar_url": user["picture"],
        }
