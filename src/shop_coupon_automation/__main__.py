import argparse
import getpass
import logging
import sys
import tomllib
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

import httpx2
from pydantic import ValidationError

from shop_coupon_automation.lidl.auth import LidlAuth, LidlAuthError, TokenStore
from shop_coupon_automation.lidl.client import LidlCouponClient
from shop_coupon_automation.lidl.models import LidlCredentials
from shop_coupon_automation.settings import AutomationSettings

_LOG_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_HTTP_TIMEOUT_SECONDS: Final = 30

logger: Final = logging.getLogger(__name__)


class Shop(StrEnum):
    LIDL = "lidl"


class LidlCommand(StrEnum):
    ACTIVATE = "activate"
    LOGIN = "login"
    COUPONS = "coupons"


class Arguments(argparse.Namespace):
    """Typed namespace for parsed command line arguments."""

    verbose: bool
    shop: str | None
    lidl_command: str | None = None


def _parse_arguments(argv: Sequence[str] | None) -> Arguments:
    parser = argparse.ArgumentParser(prog="shop-coupon-automation", description="Shop coupon automation.")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    shops = parser.add_subparsers(dest="shop")
    lidl = shops.add_parser(
        Shop.LIDL,
        help="activate all Lidl Plus coupons (default) or run a Lidl subcommand",
        description="Without a subcommand all inactive coupons are activated. "
        "Credentials in the [lidl] section of settings.toml enable unattended re-login "
        "when the stored tokens stop working.",
    )
    lidl_commands = lidl.add_subparsers(dest="lidl_command")
    lidl_commands.add_parser(LidlCommand.ACTIVATE, help="activate all inactive coupons (same as no subcommand)")
    lidl_commands.add_parser(
        LidlCommand.LOGIN, help="log in and store tokens (uses settings.toml credentials or prompts)"
    )
    lidl_commands.add_parser(LidlCommand.COUPONS, help="list coupons and their activation state")
    return parser.parse_args(argv, namespace=Arguments())


def _lidl_login(auth: LidlAuth, credentials: LidlCredentials | None) -> None:
    if credentials is None:
        credentials = {"email": input("Lidl e-mail: "), "password": getpass.getpass("Lidl password: ")}
    auth.login(credentials["email"], credentials["password"])


def _lidl_activate(coupons: LidlCouponClient) -> bool:
    summary = coupons.activate_all_coupons()
    logger.info("Activated %d coupons, %d failed", summary["activated"], summary["failed"])
    return summary["failed"] == 0


def _lidl_coupons(coupons: LidlCouponClient) -> None:
    for section in coupons.list_coupons():
        sys.stdout.write(f"{section['name']}:\n")
        for coupon in section["promotions"]:
            mark = "x" if coupon["isActivated"] else " "
            valid_until = coupon["validity"]["end"][:10]
            sys.stdout.write(f"  [{mark}] {coupon['discount']['title']:>8}  {coupon['title']}  (until {valid_until})\n")


def _run_lidl(command: LidlCommand, credentials: LidlCredentials | None) -> bool:
    with httpx2.Client(timeout=_HTTP_TIMEOUT_SECONDS) as client:
        auth = LidlAuth(client, TokenStore(TokenStore.default_path()), credentials)
        match command:
            case LidlCommand.ACTIVATE:
                return _lidl_activate(LidlCouponClient(client, auth))
            case LidlCommand.LOGIN:
                _lidl_login(auth, credentials)
            case LidlCommand.COUPONS:
                _lidl_coupons(LidlCouponClient(client, auth))
    return True


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_arguments(argv)
    logging.basicConfig(level=logging.DEBUG if arguments.verbose else logging.INFO, format=_LOG_FORMAT)
    # Transport debug logs include full response headers, too noisy even in verbose mode
    logging.getLogger("httpcore2").setLevel(logging.INFO)
    if arguments.shop is None:
        logger.info("No shop selected, use --help to list commands")
        return 0
    try:
        settings = AutomationSettings.load()
    except ValidationError, tomllib.TOMLDecodeError:
        logger.exception("Invalid settings file")
        return 1
    match Shop(arguments.shop):
        case Shop.LIDL:
            try:
                succeeded = _run_lidl(
                    LidlCommand(arguments.lidl_command or LidlCommand.ACTIVATE), settings.lidl_credentials
                )
            except LidlAuthError, httpx2.HTTPError:
                logger.exception("Lidl command failed")
                return 1
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
