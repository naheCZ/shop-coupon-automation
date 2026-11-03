from typing import Final, cast

import httpx2
from mockito import mock, when

from shop_coupon_automation.lidl.auth import LidlAuth
from shop_coupon_automation.lidl.client import LidlCouponClient

_COUPON: Final = {
    "id": "coupon-1",
    "title": "sleva",
    "description": "Cola Zero, 2l",
    "offer": "-15 %",
    "isActivated": False,
    "endValidityDate": "2026-11-01T22:59:59Z",
    "channel": "Store",
}
_LIST_PATH: Final = "/prm/api/v1/CZ/promotionslist"


def _client(requests: list[httpx2.Request], sections: list[dict[str, object]] | None = None) -> LidlCouponClient:
    listed = sections if sections is not None else [{"id": "AllStores", "titleKey": "all", "promotions": [_COUPON]}]

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx2.Response(200, json={"sections": listed})
        return httpx2.Response(200)

    auth = cast("LidlAuth", mock(LidlAuth))
    when(auth).access_token().thenReturn("ACCESS")
    return LidlCouponClient(httpx2.Client(transport=httpx2.MockTransport(handle)), auth)


def test_list_coupons_returns_sections_with_app_headers() -> None:
    requests: list[httpx2.Request] = []

    sections = _client(requests).list_coupons()

    assert sections == [{"id": "AllStores", "titleKey": "all", "promotions": [_COUPON]}]
    assert requests[0].url.path == _LIST_PATH
    assert requests[0].url.params["language"] == "cs-CZ"
    assert requests[0].headers["authorization"] == "Bearer ACCESS"
    assert requests[0].headers["country"] == "CZ"


def test_activate_coupon_posts_to_web_activation_endpoint() -> None:
    requests: list[httpx2.Request] = []

    _client(requests).activate_coupon("coupon-1")

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/prm/api/v1/CZ/promotions/coupon-1/activation"
    assert requests[0].url.params["language"] == "cs-CZ"
    assert requests[0].headers["authorization"] == "Bearer ACCESS"


def test_activate_all_coupons_activates_only_inactive_and_continues_after_failure() -> None:
    requests: list[httpx2.Request] = []
    coupons = [
        {**_COUPON, "id": "active", "isActivated": True},
        {**_COUPON, "id": "broken"},
        {**_COUPON, "id": "fine"},
    ]
    sections = [{"id": "AllStores", "titleKey": "all", "promotions": coupons}]

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx2.Response(200, json={"sections": sections})
        if "broken" in request.url.path:
            return httpx2.Response(409, text="conflict")
        return httpx2.Response(200)

    auth = cast("LidlAuth", mock(LidlAuth))
    when(auth).access_token().thenReturn("ACCESS")
    client = LidlCouponClient(httpx2.Client(transport=httpx2.MockTransport(handle)), auth)

    assert client.activate_all_coupons() == {"activated": 1, "failed": 1}
    assert [r.url.path for r in requests if r.method == "POST"] == [
        "/prm/api/v1/CZ/promotions/broken/activation",
        "/prm/api/v1/CZ/promotions/fine/activation",
    ]


def test_activate_all_coupons_activates_coupon_listed_in_two_sections_once() -> None:
    requests: list[httpx2.Request] = []
    sections: list[dict[str, object]] = [
        {"id": "OnlineShop", "titleKey": "online", "promotions": [_COUPON]},
        {"id": "AllStores", "titleKey": "all", "promotions": [_COUPON]},
    ]

    assert _client(requests, sections).activate_all_coupons() == {"activated": 1, "failed": 0}
    assert [r.url.path for r in requests if r.method == "POST"] == ["/prm/api/v1/CZ/promotions/coupon-1/activation"]
