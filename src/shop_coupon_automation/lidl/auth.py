import base64
import hashlib
import json
import logging
import os
import re
import secrets
import string
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Final, cast
from urllib.parse import parse_qs, urljoin, urlparse

import httpx2

from shop_coupon_automation.lidl import constants
from shop_coupon_automation.lidl.models import LidlCredentials, StoredTokens, TokenResponse

logger: Final = logging.getLogger(__name__)

_PKCE_ALPHABET: Final = string.ascii_letters + string.digits + "-._~"
_PKCE_VERIFIER_LENGTH: Final = 64
_MAX_REDIRECTS: Final = 10
# Refresh the access token a bit before it really expires
_EXPIRY_MARGIN_SECONDS: Final = 60
_ANTIFORGERY_PATTERN: Final = re.compile(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"')
_REDIRECT_STATUSES: Final = frozenset({301, 302, 303, 307, 308})


class LidlAuthError(Exception):
    """Login or token refresh failed."""


class TokenStore:
    """Persists Lidl Plus tokens in a JSON file readable only by the current user."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @staticmethod
    def default_path() -> Path:
        # Set by systemd for services with StateDirectory=
        state_directory = os.environ.get("STATE_DIRECTORY")
        if state_directory:
            return Path(state_directory) / "lidl_tokens.json"
        config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
        return Path(config_home) / "shop-coupon-automation" / "lidl_tokens.json"

    def load(self) -> StoredTokens | None:
        if not self._path.exists():
            return None
        return cast("StoredTokens", json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, tokens: StoredTokens) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Create the file with restricted permissions before writing secrets into it
        self._path.touch(mode=0o600, exist_ok=True)
        self._path.chmod(0o600)
        self._path.write_text(json.dumps(tokens), encoding="utf-8")


class LidlAuth:
    """Lidl Plus login (OpenID Connect authorization code + PKCE) and token refresh."""

    def __init__(
        self,
        client: httpx2.Client,
        store: TokenStore,
        credentials: LidlCredentials | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._client = client
        self._store = store
        # Optional credentials allow unattended re-login when there are no usable tokens
        self._credentials = credentials
        self._clock = clock

    def login(self, email: str, password: str) -> None:
        verifier, challenge = LidlAuth._pkce_pair()
        login_page = self._open_login_page(challenge)
        antiforgery_token = LidlAuth._extract_antiforgery_token(login_page.text)
        response = self._client.post(
            str(login_page.url),
            data={
                "DeviceId": str(uuid.uuid4()),
                # The server currently accepts an empty token, it may start enforcing reCAPTCHA one day
                "ReCaptchaToken": "",
                "Email": email,
                "PhoneNumber": "",
                "PhoneCountryCode": "",
                "Password": password,
                "RememberMe": "true",
                "Step": "1",
                "__RequestVerificationToken": antiforgery_token,
            },
            headers={
                "User-Agent": constants.BROWSER_USER_AGENT,
                "Origin": constants.ACCOUNTS_URL,
                "Referer": str(login_page.url),
            },
            follow_redirects=False,
        )
        if response.status_code not in _REDIRECT_STATUSES:
            msg = f"Login rejected (HTTP {response.status_code}), check the credentials or reCAPTCHA enforcement"
            raise LidlAuthError(msg)
        code = self._follow_to_authorization_code(response)
        tokens = self._request_tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": constants.REDIRECT_URI,
                "code_verifier": verifier,
            }
        )
        self._save(tokens)
        logger.info("Logged in to Lidl Plus")

    def access_token(self) -> str:
        stored = self._store.load()
        if stored is None:
            return self._relogin("Not logged in")
        if stored["expires_at"] - _EXPIRY_MARGIN_SECONDS > self._clock():
            return stored["access_token"]
        logger.debug("Access token expired, refreshing")
        try:
            tokens = self._request_tokens({"grant_type": "refresh_token", "refresh_token": stored["refresh_token"]})
        except LidlAuthError as error:
            return self._relogin(f"Token refresh failed ({error})")
        return self._save(tokens)["access_token"]

    def _relogin(self, reason: str) -> str:
        if self._credentials is None:
            msg = f"{reason}, run the login command or add [lidl] credentials to settings.toml"
            raise LidlAuthError(msg)
        logger.info("%s, logging in with provided credentials", reason)
        self.login(self._credentials["email"], self._credentials["password"])
        stored = self._store.load()
        if stored is None:
            msg = "Login did not store any tokens"
            raise LidlAuthError(msg)
        return stored["access_token"]

    def _open_login_page(self, code_challenge: str) -> httpx2.Response:
        params = {
            "client_id": constants.CLIENT_ID,
            "response_type": "code",
            "scope": constants.SCOPE,
            "redirect_uri": constants.REDIRECT_URI,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": secrets.token_urlsafe(16),
            "nonce": secrets.token_urlsafe(16),
            "country_code": constants.COUNTRY,
            "language": constants.LANGUAGE,
        }
        response = self._client.get(
            constants.AUTHORIZE_URL,
            params=params,
            headers={"User-Agent": constants.BROWSER_USER_AGENT, "Accept-Language": constants.LANGUAGE},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response

    def _follow_to_authorization_code(self, response: httpx2.Response) -> str:
        # The final redirect goes to the app's custom scheme, which cannot be requested, so redirects are
        # followed manually until it shows up
        for _ in range(_MAX_REDIRECTS):
            location = response.headers.get("location")
            if location is None:
                msg = f"Redirect chain ended without authorization code (HTTP {response.status_code})"
                raise LidlAuthError(msg)
            url = urljoin(str(response.url), location)
            if url.startswith(constants.REDIRECT_URI):
                return LidlAuth._extract_authorization_code(url)
            response = self._client.get(
                url, headers={"User-Agent": constants.BROWSER_USER_AGENT}, follow_redirects=False
            )
        msg = "Too many redirects during login"
        raise LidlAuthError(msg)

    def _request_tokens(self, data: dict[str, str]) -> TokenResponse:
        response = self._client.post(
            constants.TOKEN_URL,
            data=data,
            auth=(constants.CLIENT_ID, constants.CLIENT_SECRET),
            follow_redirects=False,
        )
        if response.is_error:
            msg = f"Token request failed (HTTP {response.status_code}): {response.text[:200]}"
            raise LidlAuthError(msg)
        return cast("TokenResponse", response.json())

    def _save(self, tokens: TokenResponse) -> StoredTokens:
        stored: StoredTokens = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_at": self._clock() + tokens["expires_in"],
        }
        self._store.save(stored)
        return stored

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        verifier = "".join(secrets.choice(_PKCE_ALPHABET) for _ in range(_PKCE_VERIFIER_LENGTH))
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return verifier, challenge

    @staticmethod
    def _extract_antiforgery_token(html: str) -> str:
        match = _ANTIFORGERY_PATTERN.search(html)
        if match is None:
            msg = "Login page does not contain __RequestVerificationToken, the login form has probably changed"
            raise LidlAuthError(msg)
        return match.group(1)

    @staticmethod
    def _extract_authorization_code(url: str) -> str:
        codes = parse_qs(urlparse(url).query).get("code")
        if not codes:
            msg = "Callback URL does not contain an authorization code"
            raise LidlAuthError(msg)
        return codes[0]
