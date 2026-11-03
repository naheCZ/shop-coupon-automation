import logging
from typing import Final, cast

import httpx2

from shop_coupon_automation.lidl import constants
from shop_coupon_automation.lidl.auth import LidlAuth
from shop_coupon_automation.lidl.models import ActivationSummary, Coupon, CouponSection, PromotionsList

logger: Final = logging.getLogger(__name__)


def coupon_label(coupon: Coupon) -> str:
    return f"{coupon['description']} ({coupon['offer']})"


class LidlCouponClient:
    """Minimal Lidl Plus coupons API client (web API, which lists all coupons)."""

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
            headers=self._headers(),
        )
        response.raise_for_status()

    def activate_all_coupons(self) -> ActivationSummary:
        summary: ActivationSummary = {"activated": 0, "failed": 0}
        # A coupon can appear in more than one section, activate each one only once
        inactive: dict[str, Coupon] = {}
        for section in self.list_coupons():
            for coupon in section["promotions"]:
                if not coupon["isActivated"]:
                    inactive.setdefault(coupon["id"], coupon)
        logger.info("Found %d inactive coupons", len(inactive))
        for coupon in inactive.values():
            try:
                self.activate_coupon(coupon["id"])
            except httpx2.HTTPStatusError as error:
                # One broken coupon must not stop activation of the others
                summary["failed"] += 1
                logger.warning(
                    "Failed to activate %s (HTTP %d): %s",
                    coupon_label(coupon),
                    error.response.status_code,
                    error.response.text[:200],
                )
            else:
                summary["activated"] += 1
                logger.info("Activated %s", coupon_label(coupon))
        return summary

    def _headers(self) -> dict[str, str]:
        return {**constants.APP_HEADERS, "Authorization": f"Bearer {self._auth.access_token()}"}
