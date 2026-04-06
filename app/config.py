"""Application settings loaded from environment variables.

Keeping configuration in one place makes it easier to move the project
between local Docker runs and a future production deployment.
"""

from pydantic import BaseModel


class Settings(BaseModel):
    """Small typed container for runtime configuration."""

    app_name: str = "Curriculum Planner"
    secret_key: str = "change-me"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    database_url: str = "sqlite:///data/app.db"


def get_settings() -> Settings:
    """Read settings from the environment with sensible local defaults."""

    import os

    return Settings(
        app_name=os.getenv("APP_NAME", "Curriculum Planner"),
        secret_key=os.getenv("SECRET_KEY", "change-me"),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin123"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/app.db"),
    )
