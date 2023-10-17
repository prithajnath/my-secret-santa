import urllib.parse as urlparse
from typing import Dict, Optional, TypedDict

from urllib.parse import urlencode


class OAuthUser(TypedDict):
    id: str
    first_name: str
    last_name: str
    email: str
    avatar_url: str


class OAuthHandler:
    STATE: Dict = {}

    def __init__(
        self,
        name: str,
        authorize_url: str,
        access_token_url: str,
        client_id: str,
        client_secret: str,
    ):
        self.name = name
        self.authorize_url = authorize_url
        self.access_token_url = access_token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._state = {}

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{self.name} : {self.authorize_url}"

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state: dict):
        self._state = {**self._state, **new_state}

    def flush(self, key):
        _state = {k: self._state[k] for k in self._state if k != key}
        value = self._state.get(key)
        self._state = _state
        return value

    def _oauth_url(self, params: Optional[dict] = None):
        if not params:
            params = {
                "client_id": self.client_id,
                "state": self.state,
            }

        if self.state:
            params = {"state": self.state, **params}

        url_parts = list(urlparse.urlparse(self.authorize_url))
        url_parts[4] = urlencode(params)

        oauth_url = urlparse.urlunparse(url_parts)

        return oauth_url

    ###########################################
    #    TO BE IMPLEMENTED BY SUBCLASS        #
    ###########################################

    def user_data(self) -> OAuthUser:
        pass
