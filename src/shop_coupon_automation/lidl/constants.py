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

# The web API lists every coupon (including store-only offers the app API does not return) and activates them all.
# It accepts the same bearer token as the app.
COUPONS_URL: Final = f"https://www.lidl.cz/prm/api/v1/{COUNTRY}"
PROMOTIONS_LIST_URL: Final = f"{COUPONS_URL}/promotionslist?language={LANGUAGE}"
PROMOTION_ACTIVATION_URL: Final = f"{COUPONS_URL}/promotions/{{coupon_id}}/activation?language={LANGUAGE}"

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
