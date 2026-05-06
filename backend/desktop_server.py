import os
import sys
from pathlib import Path

import uvicorn


def _default_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


def _bootstrap_env() -> None:
    """Set env before importing api so FRONTEND_DIST and data root resolve correctly."""
    app_root = _default_app_root()
    frontend_dist = app_root / "frontend" / "dist"
    data_root = Path(os.getenv("LOCALAPPDATA", str(app_root))) / "MockGenerator" / "data"
    os.environ.setdefault("MOCKGENERATOR_DATA_ROOT", str(data_root))
    os.environ.setdefault("MOCKGENERATOR_FRONTEND_DIST", str(frontend_dist))
    os.environ.setdefault("FRONTEND_ORIGIN", "http://127.0.0.1:8000")
    os.environ.setdefault("MOCKGENERATOR_RUN_INPROCESS", "1")


_bootstrap_env()

# Import app object directly so PyInstaller bundles api.py (uvicorn "api:app" fails in frozen exe).
from api import app  # noqa: E402


def main() -> None:
    backend_dir = _default_app_root() / "backend"
    port = int(os.getenv("MOCKGENERATOR_PORT", "8000"))

    os.chdir(backend_dir)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
