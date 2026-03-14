from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "ASHORT_", "env_file": ".env", "env_file_encoding": "utf-8"}

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

    # Paths
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = project_root / "data"
    seed_dir: Path = project_root / "seed"


settings = Settings()
