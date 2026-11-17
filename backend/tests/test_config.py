import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {"database_url": "postgresql+psycopg://u:p@localhost/db"}


def test_production_refuses_a_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(app_env="production", secret_key="change-me-" + "x" * 30, **BASE)


def test_production_accepts_a_real_secret_and_development_is_not_restricted() -> None:
    assert Settings(app_env="production", secret_key="a" * 64, **BASE).is_production
    assert not Settings(
        app_env="development", secret_key="change-me-" + "x" * 30, **BASE
    ).is_production


def test_the_secret_must_be_long_enough() -> None:
    with pytest.raises(ValidationError):
        Settings(secret_key="short", **BASE)


def test_database_url_must_use_the_async_driver() -> None:
    with pytest.raises(ValidationError, match="psycopg"):
        Settings(secret_key="a" * 40, database_url="postgresql://u:p@localhost/db")
