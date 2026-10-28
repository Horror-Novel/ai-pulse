"""Disposable real HTTP server for browser tests; never touches the demo database."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    with TemporaryDirectory(prefix="ai-pulse-e2e-") as directory:
        os.environ.update({
            "DATABASE_URL": "sqlite:///" + (Path(directory) / "test.db").as_posix(),
            "APP_ENV": "development",
            "AI_MODE": "mock",
            "AI_MOCK_SCENARIO": "valid",
            "SECRET_KEY": "browser-test-key-at-least-32-characters",
            "CORS_ORIGINS": "http://127.0.0.1:5174",
        })
        from app import seed
        seed.run()
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001)
