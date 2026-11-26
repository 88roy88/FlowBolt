import logging
import tomllib
from functools import cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from flow44.config import settings

logger = logging.getLogger(__name__)

_NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AppType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: _NonEmptyStr
    name: _NonEmptyStr
    examples: list[_NonEmptyStr] = []
    icon: _NonEmptyStr

    @field_validator("icon")
    @classmethod
    def _is_svg(cls, icon: str) -> str:
        if not icon.startswith("<svg"):
            raise ValueError("icon must be an <svg> element")
        return icon


class PublishFormConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_types: list[AppType] = Field(min_length=1)
    publish_reasons: list[_NonEmptyStr] = []

    @field_validator("app_types")
    @classmethod
    def _unique_ids(cls, app_types: list[AppType]) -> list[AppType]:
        ids = [app_type.id for app_type in app_types]
        if len(set(ids)) != len(ids):
            raise ValueError("app type ids must be unique")
        return app_types


def load_publish_form_config(path: Path) -> PublishFormConfig:
    return PublishFormConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8-sig")))


@cache
def get_publish_form_config() -> PublishFormConfig:
    return load_publish_form_config(Path(settings.PUBLISH_FORM_CONFIG_PATH))


def validate_publish_form_config() -> None:
    try:
        get_publish_form_config()
    except (OSError, ValueError):  # unreadable file, bad TOML or bad contents
        logger.exception("Invalid publish form config: %s", settings.PUBLISH_FORM_CONFIG_PATH)
        raise
