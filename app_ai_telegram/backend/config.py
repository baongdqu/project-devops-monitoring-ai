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

    # LLM Observability & Tracing (LangSmith / Langfuse)
    LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() in ("true", "1", "yes")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "devops-ai-monitoring")
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    ENABLE_AUTO_EVAL: bool = os.getenv("ENABLE_AUTO_EVAL", "true").lower() in ("true", "1", "yes")

    PORT: int = int(os.getenv("PORT", "80"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    WORKSPACE_DIR: Path = BASE_DIR / "workspace"

settings = Settings()

# Tự động kích hoạt LangSmith Tracing nếu có cấu hình
if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    print(f"📡 LangSmith Tracing đã kích hoạt cho Project: '{settings.LANGCHAIN_PROJECT}'")

def is_admin(user_id: int | str) -> bool:
    """Kiểm tra quyền Admin RBAC cho các tác vụ thay đổi hạ tầng."""
    if not settings.TELEGRAM_ADMIN_ID:
        return True
    return str(user_id).strip() == str(settings.TELEGRAM_ADMIN_ID).strip()

# Đảm bảo các thư mục dữ liệu tồn tại
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
