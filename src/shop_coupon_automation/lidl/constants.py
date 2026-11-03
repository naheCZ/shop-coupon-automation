# Lidl Plus API constants.
# Reference (not a dependency): https://github.com/zsobix/lidlplus-api/blob/main/lidlplus_api/api.py
# Lidl changes these from time to time, keep them all in this one place.
from typing import Final

ACCOUNTS_URL: Final = "https://accounts.lidl.com"
AUTHORIZE_URL: Final = f"{ACCOUNTS_URL}/connect/authorize"
TOKEN_URL: Final = f"{ACCOUNTS_URL}/connect/token"

CLIENT_ID: Final = "LidlPlusNativeClient"
# Public secret of the native app client, not a credential
CLIENT_SECRET: Final = "secret"  # noqa: S105
REDIRECT_URI: Final = "com.lidlplus.app://callback"
SCOPE: Final = "openid profile offline_access lpprofile lpapis"

COUNTRY: Final = "CZ"
LANGUAGE: Final = "cs-CZ"

# The login form is a regular web page, so it is requested as a desktop browser
BROWSER_USER_AGENT: Final = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

COUPONS_URL: Final = "https://coupons.lidlplus.com/app/api"
PROMOTIONS_LIST_URL: Final = f"{COUPONS_URL}/v4/promotionslist"
PROMOTION_ACTIVATION_URL: Final = f"{COUPONS_URL}/v2/promotions/{{coupon_id}}/activation"

# Headers sent by the Lidl Plus Android app
APP_HEADERS: Final = {
    "App": "com.lidl.eci.lidlplus",
    "App-Version": "16.43.4",
    "Operating-System": "Android",
    "OS-Version": "16",
    "User-Agent": "okhttp/5.4.0",
    "Accept-Language": LANGUAGE,
    "country": COUNTRY,
}
