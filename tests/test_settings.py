from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from shop_coupon_automation.settings import AutomationSettings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolated_settings_locations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Keep real settings files (working directory, user config) out of the tests
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("CONFIGURATION_DIRECTORY", raising=False)


def test_load_without_settings_file_returns_defaults() -> None:
    settings = AutomationSettings.load()

    assert settings.lidl is None
    assert settings.lidl_credentials is None


def test_load_lidl_credentials_from_working_directory(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[lidl]\nemail = "user@example.com"\npassword = "secret-password"\n')

    settings = AutomationSettings.load()

    assert settings.lidl_credentials == {"email": "user@example.com", "password": "secret-password"}
    assert "secret-password" not in repr(settings)


def test_load_prefers_systemd_configuration_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[lidl]\nemail = "cwd@example.com"\npassword = "p"\n')
    systemd_dir = tmp_path / "etc"
    systemd_dir.mkdir()
    (systemd_dir / "settings.toml").write_text('[lidl]\nemail = "systemd@example.com"\npassword = "p"\n')
    monkeypatch.setenv("CONFIGURATION_DIRECTORY", str(systemd_dir))

    settings = AutomationSettings.load()

    assert settings.lidl is not None
    assert settings.lidl["email"] == "systemd@example.com"


def test_load_user_config_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "shop-coupon-automation"
    config_dir.mkdir(parents=True)
    (config_dir / "settings.toml").write_text('[lidl]\nemail = "user@example.com"\npassword = "p"\n')

    settings = AutomationSettings.load()

    assert settings.lidl is not None
    assert settings.lidl["email"] == "user@example.com"


def test_load_incomplete_lidl_section_raises(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text('[lidl]\nemail = "user@example.com"\n')

    with pytest.raises(ValidationError):
        AutomationSettings.load()
