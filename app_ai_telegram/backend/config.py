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

    # DevOps Proactive Health Monitoring
    TARGET_APP_URL: str = os.getenv("TARGET_APP_URL", "https://urlshortener-app.redmoss-b81863cc.eastasia.azurecontainerapps.io")
    MONITOR_INTERVAL_SECONDS: int = int(os.getenv("MONITOR_INTERVAL_SECONDS", "60"))
    ENABLE_PROACTIVE_MONITORING: bool = os.getenv("ENABLE_PROACTIVE_MONITORING", "true").lower() in ("true", "1", "yes")

    PORT: int = int(os.getenv("PORT", "80"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    WORKSPACE_DIR: Path = BASE_DIR / "workspace"

settings = Settings()

def is_admin(user_id: int | str) -> bool:
    """Kiểm tra quyền Admin RBAC cho các tác vụ thay đổi hạ tầng."""
    if not settings.TELEGRAM_ADMIN_ID:
        return True
    return str(user_id).strip() == str(settings.TELEGRAM_ADMIN_ID).strip()

# Đảm bảo các thư mục dữ liệu tồn tại
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
