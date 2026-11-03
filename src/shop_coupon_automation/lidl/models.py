from typing import NotRequired, TypedDict


class TokenResponse(TypedDict):
    """Response of the OpenID Connect token endpoint."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str
    id_token: NotRequired[str]


class LidlCredentials(TypedDict):
    email: str
    password: str


class StoredTokens(TypedDict):
    """Tokens persisted between runs."""

    access_token: str
    refresh_token: str
    expires_at: float


class CouponDiscount(TypedDict):
    title: str
    description: str


class CouponValidity(TypedDict):
    start: str
    end: str


class Coupon(TypedDict):
    """Single promotion from the promotions list (only the fields we use)."""

    id: str
    promotionId: str
    title: str
    discount: CouponDiscount
    validity: CouponValidity
    isActivated: bool
    channels: list[str]


class ActivationSummary(TypedDict):
    activated: int
    failed: int


class CouponSection(TypedDict):
    name: str
    promotions: list[Coupon]


class PromotionsList(TypedDict):
    sections: list[CouponSection]
