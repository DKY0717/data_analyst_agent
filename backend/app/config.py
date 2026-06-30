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


def _get_csv_list(env_key: str, default: list[str]) -> list[str]:
    """读取逗号分隔配置；空值使用安全默认值，避免生产误退回通配符。"""
    val = os.getenv(env_key, "").strip()
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


def _get_optional_non_negative_float(env_key: str) -> float | None:
    """读取可选非负价格；空值表示不进行成本估算。"""
    val = os.getenv(env_key, "").strip()
    if not val:
        return None
    try:
        parsed = float(val)
    except ValueError:
        raise ValueError(f"Environment variable {env_key} must be a number, got: {val}")
    if parsed < 0:
        raise ValueError(f"Environment variable {env_key} must be non-negative, got: {val}")
    return parsed


class Settings:
    """Application settings"""

    # API Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = _get_int("APP_PORT", 8000)
    DEBUG: bool = _get_bool("DEBUG", False)
    # 演示登录只服务本地面试展示，默认关闭，避免生产环境暴露角色切换入口。
    AUTH_DEMO_ENABLED: bool = _get_bool("AUTH_DEMO_ENABLED", False)
    # 密码登录默认关闭；开启时必须通过环境变量显式配置管理员用户名和密码。
    AUTH_PASSWORD_LOGIN_ENABLED: bool = _get_bool("AUTH_PASSWORD_LOGIN_ENABLED", False)
    AUTH_ADMIN_USERNAME: str = os.getenv("AUTH_ADMIN_USERNAME", "")
    AUTH_ADMIN_PASSWORD: str = os.getenv("AUTH_ADMIN_PASSWORD", "")
    # 默认只允许本地前端开发地址；生产应通过环境变量配置真实前端域名。
    CORS_ALLOW_ORIGINS: list[str] = _get_csv_list(
        "CORS_ALLOW_ORIGINS",
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
    )
    DATA_PERMISSION_POLICY_PATH: str = os.getenv("DATA_PERMISSION_POLICY_PATH", "")

    # Database Configuration
    # 支持两种后端: duckdb (嵌入式) 或 postgresql (生产级)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "duckdb:///./data/database.duckdb")
    DATABASE_BACKEND: str = os.getenv("DATABASE_BACKEND", "")  # "duckdb" 或 "postgresql"，留空自动检测

    # PostgreSQL 专用配置（仅 DATABASE_BACKEND=postgresql 时生效）
    PG_HOST: str = os.getenv("PG_HOST", "localhost")
    PG_PORT: int = _get_int("PG_PORT", 5432)
    PG_USER: str = os.getenv("PG_USER", "postgres")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "postgres")
    PG_DATABASE: str = os.getenv("PG_DATABASE", "data_analyst_agent")

    # LLM API Configuration (OpenAI 兼容协议，支持 MiMo、Qwen 等)
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_URL: str = os.getenv("QWEN_API_URL", "https://token-plan-cn.xiaomimimo.com/v1/chat/completions")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "mimo-v2.5-pro")
    QWEN_INPUT_PRICE_PER_MILLION_TOKENS: float | None = _get_optional_non_negative_float(
        "QWEN_INPUT_PRICE_PER_MILLION_TOKENS"
    )
    QWEN_OUTPUT_PRICE_PER_MILLION_TOKENS: float | None = _get_optional_non_negative_float(
        "QWEN_OUTPUT_PRICE_PER_MILLION_TOKENS"
    )

    # SQL Configuration
    SQL_TIMEOUT: int = _get_int("SQL_TIMEOUT", 30)
    SQL_MAX_ROWS: int = _get_int("SQL_MAX_ROWS", 1000)
    SQL_MAX_RETRIES: int = _get_int("SQL_MAX_RETRIES", 3)
    # 生产可打开子进程沙箱隔离 SQL 执行；默认关闭，保留本地开发和测试的简单路径。
    SANDBOX_MODE: bool = _get_bool("SANDBOX_MODE", False)

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
