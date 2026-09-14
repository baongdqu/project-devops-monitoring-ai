import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_ID: str = os.getenv("TELEGRAM_ADMIN_ID", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "15"))
    CODE_EXECUTION_TIMEOUT: int = int(os.getenv("CODE_EXECUTION_TIMEOUT", "30"))

    PORT: int = int(os.getenv("PORT", "80"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    WORKSPACE_DIR: Path = BASE_DIR / "workspace"

settings = Settings()

# Đảm bảo các thư mục dữ liệu tồn tại
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
