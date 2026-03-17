from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "env_prefix": "ASHORT_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    # Database
    db_url: str = "sqlite:///data/a_share_short.db"

    # AKShare
    akshare_request_interval: float = 0.6  # seconds between API calls
    akshare_max_retries: int = 3

    # Data
    history_months: int = 6  # how many months of historical data to load

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # AI API. Prefer standard OpenAI env vars, but keep project-prefixed vars compatible.
    ai_api_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "ASHORT_AI_API_BASE_URL"),
    )
    ai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "ASHORT_AI_API_KEY"),
    )
    ai_model: str = Field(
        default="gpt-5.4",
        validation_alias=AliasChoices("OPENAI_MODEL", "ASHORT_AI_MODEL"),
    )
    ai_max_retries: int = 3
    ai_timeout: int = 60
    ai_temperature: float = 0.1
    ai_reasoning_effort: str = Field(
        default="medium",
        validation_alias=AliasChoices(
            "OPENAI_REASONING_EFFORT",
            "ASHORT_AI_REASONING_EFFORT",
        ),
    )
    ai_use_env_proxy: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "OPENAI_USE_ENV_PROXY",
            "ASHORT_AI_USE_ENV_PROXY",
        ),
    )
    ai_user_agent: str = Field(
        default="curl/8.0.1",
        validation_alias=AliasChoices(
            "OPENAI_USER_AGENT",
            "ASHORT_AI_USER_AGENT",
        ),
    )

    # Network proxy. Support both project-prefixed vars and standard proxy vars.
    http_proxy: str = Field(
        default="",
        validation_alias=AliasChoices("ASHORT_HTTP_PROXY", "HTTP_PROXY"),
    )
    https_proxy: str = Field(
        default="",
        validation_alias=AliasChoices("ASHORT_HTTPS_PROXY", "HTTPS_PROXY"),
    )

    # Paths
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = project_root / "data"
    seed_dir: Path = project_root / "seed"


settings = Settings()
