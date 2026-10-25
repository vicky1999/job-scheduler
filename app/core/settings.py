from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    MAX_RETRIES: int  = 3
    MAX_WORKERS: int = 4
    POLL_INTERVAL: float = 1
    JOB_LEASE_DURATION: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()