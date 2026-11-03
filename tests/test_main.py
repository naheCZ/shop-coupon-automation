from typing import TYPE_CHECKING, cast

import pytest
from mockito import mock, when

from shop_coupon_automation.__main__ import _lidl_activate, _lidl_coupons, main
from shop_coupon_automation.lidl.client import LidlCouponClient

if TYPE_CHECKING:
    from pathlib import Path


def test_main_returns_success() -> None:
    assert main([]) == 0


def test_main_verbose_returns_success() -> None:
    assert main(["--verbose"]) == 0


def test_lidl_coupons_prints_activation_state(capsys: pytest.CaptureFixture[str]) -> None:
    coupons = cast("LidlCouponClient", mock(LidlCouponClient))
    when(coupons).list_coupons().thenReturn(
        [
            {
                "name": "AllStores",
                "promotions": [
                    {
                        "id": "c1",
                        "promotionId": "p1",
                        "title": "Cola Zero, 2l",
                        "discount": {"title": "-15 %", "description": "sleva"},
                        "validity": {"start": "2026-10-26T00:00:00Z", "end": "2026-11-01T22:59:59Z"},
                        "isActivated": True,
                        "channels": ["Store"],
                    }
                ],
            }
        ]
    )

    _lidl_coupons(coupons)

    assert capsys.readouterr().out == "AllStores:\n  [x]    -15 %  Cola Zero, 2l  (until 2026-11-01)\n"


@pytest.mark.parametrize("argv", [["lidl"], ["lidl", "activate"], ["lidl", "coupons"]])
def test_lidl_command_without_login_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, argv: list[str]) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("STATE_DIRECTORY", raising=False)
    monkeypatch.delenv("CONFIGURATION_DIRECTORY", raising=False)
    # Without a settings file there are no credentials, so no real login is attempted
    monkeypatch.chdir(tmp_path)

    assert main(argv) == 1


def test_lidl_activate_reports_failures() -> None:
    coupons = cast("LidlCouponClient", mock(LidlCouponClient))
    when(coupons).activate_all_coupons().thenReturn({"activated": 2, "failed": 1})

    assert _lidl_activate(coupons) is False


def test_invalid_settings_file_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CONFIGURATION_DIRECTORY", raising=False)
    (tmp_path / "settings.toml").write_text("[lidl]\nemail = 1\n")

    assert main(["lidl"]) == 1
