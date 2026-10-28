import os
import secrets

# Load .env if present (very small loader, no extra dependency)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

APP_ENV = os.getenv("APP_ENV", "development")
SECRET_KEY = os.getenv("SECRET_KEY", "")
if len(SECRET_KEY) < 32 or SECRET_KEY == "ai-pulse-dev-secret":
    if APP_ENV != "development":
        raise RuntimeError("Set SECRET_KEY to a random secret of at least 32 characters")
    # A process-local development key avoids a publicly known signing secret.
    SECRET_KEY = secrets.token_urlsafe(48)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aipulse.db")
AI_MODE = os.getenv("AI_MODE", "mock")  # "mock" or "live"
if AI_MODE not in {"mock", "live"}:
    raise RuntimeError("AI_MODE must be mock or live")
LLM_API_URL = os.getenv("LLM_API_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
TOKEN_HOURS = 12
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
