import stat
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qs

import httpx2
import pytest

from shop_coupon_automation.lidl import constants
from shop_coupon_automation.lidl.auth import LidlAuth, LidlAuthError, TokenStore

if TYPE_CHECKING:
    from pathlib import Path

    from shop_coupon_automation.lidl.models import StoredTokens

_NOW: Final = 1_000_000.0
_LOGIN_URL: Final = f"{constants.ACCOUNTS_URL}/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fx%3D1"
_LOGIN_PAGE: Final = '<form><input name="__RequestVerificationToken" type="hidden" value="ANTIFORGERY" /></form>'
_TOKENS_JSON: Final = {
    "access_token": "new-access",
    "refresh_token": "new-refresh",
    "expires_in": 1200,
    "token_type": "Bearer",
    "scope": constants.SCOPE,
}


def _login_handler(requests: list[httpx2.Request], login_status: int = 302) -> httpx2.MockTransport:
    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        match (request.method, request.url.path):
            case ("GET", "/connect/authorize"):
                return httpx2.Response(302, headers={"location": _LOGIN_URL})
            case ("GET", "/Account/Login"):
                return httpx2.Response(200, text=_LOGIN_PAGE)
            case ("POST", "/Account/Login"):
                return httpx2.Response(login_status, headers={"location": "/connect/authorize/callback?x=1"})
            case ("GET", "/connect/authorize/callback"):
                return httpx2.Response(302, headers={"location": f"{constants.REDIRECT_URI}?code=AUTH-CODE&state=s"})
            case ("POST", "/connect/token"):
                return httpx2.Response(200, json=_TOKENS_JSON)
            case _:
                return httpx2.Response(404)

    return httpx2.MockTransport(handle)


def _auth(transport: httpx2.MockTransport, store: TokenStore) -> LidlAuth:
    return LidlAuth(httpx2.Client(transport=transport), store, clock=lambda: _NOW)


def test_login_exchanges_code_and_stores_tokens(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    store = TokenStore(tmp_path / "tokens.json")

    _auth(_login_handler(requests), store).login("user@example.com", "secret-password")

    login_form = parse_qs(next(r for r in requests if r.url.path == "/Account/Login" and r.method == "POST").content)
    assert login_form[b"__RequestVerificationToken"] == [b"ANTIFORGERY"]
    assert login_form[b"Email"] == [b"user@example.com"]
    token_request = requests[-1]
    token_form = parse_qs(token_request.content)
    assert token_form[b"grant_type"] == [b"authorization_code"]
    assert token_form[b"code"] == [b"AUTH-CODE"]
    assert token_request.headers["authorization"].startswith("Basic ")
    assert store.load() == {"access_token": "new-access", "refresh_token": "new-refresh", "expires_at": _NOW + 1200}


def test_login_rejected_raises(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")

    with pytest.raises(LidlAuthError, match="Login rejected"):
        _auth(_login_handler([], login_status=200), store).login("user@example.com", "wrong")
    assert store.load() is None


def test_missing_antiforgery_token_raises() -> None:
    with pytest.raises(LidlAuthError, match="__RequestVerificationToken"):
        LidlAuth._extract_antiforgery_token("<html></html>")  # noqa: SLF001


def test_access_token_returns_valid_stored_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save({"access_token": "valid", "refresh_token": "r", "expires_at": _NOW + 600})

    assert _auth(_login_handler([]), store).access_token() == "valid"


def test_access_token_refreshes_expired_token(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    store = TokenStore(tmp_path / "tokens.json")
    store.save({"access_token": "expired", "refresh_token": "old-refresh", "expires_at": _NOW - 1})

    assert _auth(_login_handler(requests), store).access_token() == "new-access"
    assert parse_qs(requests[0].content) == {b"grant_type": [b"refresh_token"], b"refresh_token": [b"old-refresh"]}
    stored: StoredTokens | None = store.load()
    assert stored is not None
    assert stored["refresh_token"] == "new-refresh"  # noqa: S105


def test_access_token_without_login_raises(tmp_path: Path) -> None:
    with pytest.raises(LidlAuthError, match="Not logged in"):
        _auth(_login_handler([]), TokenStore(tmp_path / "tokens.json")).access_token()


def test_token_store_file_is_private(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "tokens.json"

    TokenStore(path).save({"access_token": "a", "refresh_token": "r", "expires_at": 0.0})

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_access_token_logs_in_with_credentials_when_not_logged_in(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    auth = LidlAuth(
        httpx2.Client(transport=_login_handler([])),
        store,
        {"email": "user@example.com", "password": "secret-password"},
        clock=lambda: _NOW,
    )

    assert auth.access_token() == "new-access"
    assert store.load() is not None


def test_access_token_logs_in_with_credentials_when_refresh_fails(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    login = _login_handler(requests)

    def handle(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/connect/token" and b"refresh_token" in request.content:
            requests.append(request)
            return httpx2.Response(400, json={"error": "invalid_grant"})
        return login.handle_request(request)

    store = TokenStore(tmp_path / "tokens.json")
    store.save({"access_token": "expired", "refresh_token": "revoked", "expires_at": _NOW - 1})
    auth = LidlAuth(
        httpx2.Client(transport=httpx2.MockTransport(handle)),
        store,
        {"email": "user@example.com", "password": "secret-password"},
        clock=lambda: _NOW,
    )

    assert auth.access_token() == "new-access"
    assert any(r.method == "POST" and r.url.path == "/Account/Login" for r in requests)


def test_access_token_refresh_failure_without_credentials_raises(tmp_path: Path) -> None:
    def handle(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": "invalid_grant"})

    store = TokenStore(tmp_path / "tokens.json")
    store.save({"access_token": "expired", "refresh_token": "revoked", "expires_at": _NOW - 1})

    with pytest.raises(LidlAuthError, match="Token refresh failed"):
        _auth(httpx2.MockTransport(handle), store).access_token()


def test_token_store_default_path_prefers_systemd_state_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))

    assert TokenStore.default_path() == tmp_path / "lidl_tokens.json"


def test_token_store_default_path_uses_xdg_config_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("STATE_DIRECTORY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert TokenStore.default_path() == tmp_path / "shop-coupon-automation" / "lidl_tokens.json"
