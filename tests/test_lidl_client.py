import json
from typing import Final, cast

import httpx2
from mockito import mock, when

from shop_coupon_automation.lidl.auth import LidlAuth
from shop_coupon_automation.lidl.client import LidlCouponClient

_COUPON: Final = {
    "id": "coupon-1",
    "promotionId": "promotion-1",
    "title": "Cola Zero, 2l",
    "discount": {"title": "-15 %", "description": "sleva"},
    "validity": {"start": "2026-10-26T00:00:00Z", "end": "2026-11-01T22:59:59Z"},
    "isActivated": False,
    "channels": ["Store"],
}


def _client(requests: list[httpx2.Request]) -> LidlCouponClient:
    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx2.Response(200, json={"sections": [{"name": "AllStores", "promotions": [_COUPON]}]})
        return httpx2.Response(200)

    auth = cast("LidlAuth", mock(LidlAuth))
    when(auth).access_token().thenReturn("ACCESS")
    return LidlCouponClient(httpx2.Client(transport=httpx2.MockTransport(handle)), auth)


def test_list_coupons_returns_sections_with_app_headers() -> None:
    requests: list[httpx2.Request] = []

    sections = _client(requests).list_coupons()

    assert sections == [{"name": "AllStores", "promotions": [_COUPON]}]
    assert requests[0].headers["authorization"] == "Bearer ACCESS"
    assert requests[0].headers["country"] == "CZ"
    assert requests[0].headers["app"] == "com.lidl.eci.lidlplus"


def test_activate_coupon_posts_to_activation_endpoint() -> None:
    requests: list[httpx2.Request] = []

    _client(requests).activate_coupon("coupon-1")

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/app/api/v2/promotions/coupon-1/activation"
    assert json.loads(requests[0].content) == {"articleSelection": []}
    assert requests[0].headers["action-location"] == "app_couponslist"


def test_activate_all_coupons_activates_only_inactive_and_continues_after_failure() -> None:
    requests: list[httpx2.Request] = []
    coupons = [
        {**_COUPON, "id": "active", "isActivated": True},
        {**_COUPON, "id": "broken"},
        {**_COUPON, "id": "fine"},
    ]

    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx2.Response(200, json={"sections": [{"name": "AllStores", "promotions": coupons}]})
        if "broken" in request.url.path:
            return httpx2.Response(409, text="conflict")
        return httpx2.Response(200)

    auth = cast("LidlAuth", mock(LidlAuth))
    when(auth).access_token().thenReturn("ACCESS")
    client = LidlCouponClient(httpx2.Client(transport=httpx2.MockTransport(handle)), auth)

    assert client.activate_all_coupons() == {"activated": 1, "failed": 1}
    assert [r.url.path for r in requests if r.method == "POST"] == [
        "/app/api/v2/promotions/broken/activation",
        "/app/api/v2/promotions/fine/activation",
    ]
