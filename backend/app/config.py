import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Application settings"""

    # API Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "duckdb:///./data/database.duckdb")

    # Qwen API Configuration
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_API_URL: str = os.getenv("QWEN_API_URL", "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-turbo")

    # SQL Configuration
    SQL_TIMEOUT: int = int(os.getenv("SQL_TIMEOUT", "30"))
    SQL_MAX_ROWS: int = int(os.getenv("SQL_MAX_ROWS", "1000"))
    SQL_MAX_RETRIES: int = int(os.getenv("SQL_MAX_RETRIES", "3"))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    LOG_DIR: Path = BASE_DIR / "logs"

settings = Settings()

# Create directories if they don't exist
settings.DATA_DIR.mkdir(exist_ok=True)
settings.LOG_DIR.mkdir(exist_ok=True)
