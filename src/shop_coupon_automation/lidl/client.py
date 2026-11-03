import logging
from typing import Final, cast

import httpx2

from shop_coupon_automation.lidl import constants
from shop_coupon_automation.lidl.auth import LidlAuth
from shop_coupon_automation.lidl.models import ActivationSummary, CouponSection, PromotionsList

logger: Final = logging.getLogger(__name__)


class LidlCouponClient:
    """Minimal Lidl Plus coupons API client."""

    def __init__(self, client: httpx2.Client, auth: LidlAuth) -> None:
        self._client = client
        self._auth = auth

    def list_coupons(self) -> list[CouponSection]:
        response = self._client.get(constants.PROMOTIONS_LIST_URL, headers=self._headers())
        response.raise_for_status()
        return cast("PromotionsList", response.json())["sections"]

    def activate_coupon(self, coupon_id: str) -> None:
        response = self._client.post(
            constants.PROMOTION_ACTIVATION_URL.format(coupon_id=coupon_id),
            json={"articleSelection": []},
            headers={**self._headers(), "action-location": "app_couponslist"},
        )
        response.raise_for_status()

    def activate_all_coupons(self) -> ActivationSummary:
        summary: ActivationSummary = {"activated": 0, "failed": 0}
        inactive = [
            coupon for section in self.list_coupons() for coupon in section["promotions"] if not coupon["isActivated"]
        ]
        logger.info("Found %d inactive coupons", len(inactive))
        for coupon in inactive:
            try:
                self.activate_coupon(coupon["id"])
            except httpx2.HTTPStatusError as error:
                # One broken coupon must not stop activation of the others
                summary["failed"] += 1
                logger.warning(
                    "Failed to activate %r (HTTP %d): %s",
                    coupon["title"],
                    error.response.status_code,
                    error.response.text[:200],
                )
            else:
                summary["activated"] += 1
                logger.info("Activated %r", coupon["title"])
        return summary

    def _headers(self) -> dict[str, str]:
        return {**constants.APP_HEADERS, "Authorization": f"Bearer {self._auth.access_token()}"}
