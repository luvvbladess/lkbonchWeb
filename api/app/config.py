from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://lkbonch:lkbonch@localhost:5432/lkbonch"
    jwt_secret: str = "dev-only-change-me"
    cors_origins: str = "http://localhost:4200"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    file_dir: str = "data/files"
    expose_activation_codes: bool = False
    bootstrap_admin_login: str = ""
    bootstrap_admin_password: str = ""
    max_upload_bytes: int = 20 * 1024 * 1024


settings = Settings()
