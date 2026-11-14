import sys
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    port: int = Field(default=8000, description="Server listen port (1..65535)")
    database_url: str = Field(default="", description="PostgreSQL database URL")
    mongodb_uri: str = Field(default="", description="MongoDB connection URI")
    redis_url: str = Field(default="", description="Redis connection URL")
    jwt_secret: str = Field(default="", description="JWT secret key")

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError(f"PORT must be between 1 and 65535, got {v}")
        return v


def load_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        sys.stderr.write(
            f"\n[FAIL-FAST CONFIG ERROR] Invalid PORT.\n"
            f"Set PORT in .env (example: PORT=8000).\n"
            f"Error details: {exc}\n\n"
        )
        sys.exit(1)


settings = load_settings()

