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


class Coupon(TypedDict):
    """Single promotion from the web promotions list (only the fields we use)."""

    id: str
    title: str
    # Product name, e.g. "Cola Zero, 2l"
    description: str
    # Discount label, e.g. "-15 %" or a price
    offer: str
    isActivated: bool
    endValidityDate: str
    channel: str


class ActivationSummary(TypedDict):
    activated: int
    failed: int


class CouponSection(TypedDict):
    id: str
    titleKey: str
    promotions: list[Coupon]


class PromotionsList(TypedDict):
    sections: list[CouponSection]
