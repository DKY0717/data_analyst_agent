import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_int(env_key: str, default: int) -> int:
    val = os.getenv(env_key, str(default))
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"Environment variable {env_key} must be an integer, got: {val}")


def _get_bool(env_key: str, default: bool) -> bool:
    val = os.getenv(env_key, str(default)).lower()
    return val in ("true", "1", "yes", "on")


class Settings:
    """Application settings"""

    # API Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = _get_int("APP_PORT", 8000)
    DEBUG: bool = _get_bool("DEBUG", False)

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "duckdb:///./data/database.duckdb")

    # Qwen API Configuration
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_URL: str = os.getenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-turbo")

    # SQL Configuration
    SQL_TIMEOUT: int = _get_int("SQL_TIMEOUT", 30)
    SQL_MAX_ROWS: int = _get_int("SQL_MAX_ROWS", 1000)
    SQL_MAX_RETRIES: int = _get_int("SQL_MAX_RETRIES", 3)

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Paths
    PROJECT_ROOT: str = os.getenv("PROJECT_ROOT", "")
    BASE_DIR: Path = Path(PROJECT_ROOT) if PROJECT_ROOT else Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOG_DIR: Path = BASE_DIR / "logs"


settings = Settings()

__all__ = ["settings", "ensure_directories"]

if not settings.QWEN_API_KEY:
    logger.warning("QWEN_API_KEY is not set. LLM calls will fail.")


def ensure_directories():
    """Create data and logs directories. Call at application startup."""
    settings.DATA_DIR.mkdir(exist_ok=True)
    settings.LOG_DIR.mkdir(exist_ok=True)
