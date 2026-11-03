import logging
import os
import tomllib
from pathlib import Path
from typing import Final, Self, TypedDict

from platformdirs import user_config_path
from pydantic import BaseModel, SecretStr

from shop_coupon_automation.lidl.models import LidlCredentials

_APP_NAME: Final = "shop-coupon-automation"
_FILE_NAME: Final = "settings.toml"

logger: Final = logging.getLogger(__name__)


class LidlInfo(TypedDict):
    email: str
    password: SecretStr


class AutomationSettings(BaseModel):
    lidl: LidlInfo | None = None

    @classmethod
    def load(cls) -> Self:
        settings_path = cls._find_settings_file()
        if settings_path is None:
            logger.debug("No %s found, using default settings", _FILE_NAME)
            return cls()

        logger.debug("Loading settings from %s", settings_path)
        with settings_path.open("rb") as settings_file:
            settings = tomllib.load(settings_file)

        return cls(**settings)

    @classmethod
    def _find_settings_file(cls) -> Path | None:
        candidates = [Path(_FILE_NAME), user_config_path(_APP_NAME) / _FILE_NAME]
        # Set by systemd for services with ConfigurationDirectory=
        configuration_directory = os.environ.get("CONFIGURATION_DIRECTORY")
        if configuration_directory:
            candidates.insert(0, Path(configuration_directory) / _FILE_NAME)

        for candidate in candidates:
            if candidate.is_file():
                return candidate

        return None

    @property
    def lidl_credentials(self) -> LidlCredentials | None:
        if self.lidl is None:
            return None
        return {"email": self.lidl["email"], "password": self.lidl["password"].get_secret_value()}
