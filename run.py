import os
import uvicorn
from app.main import app  # FastAPI app


def _get_bind_host() -> str:
    return os.environ.get("HOST", "127.0.0.1")


def _get_bind_port() -> int:
    try:
        return int(os.environ.get("PORT", "8000"))
    except Exception:
        return 8000


if __name__ == "__main__":
    # Use module path string for reload compatibility, but keep the already-imported app
    # Mapping: the current module exposes "app" imported from app.main above
    uvicorn.run(
        "run:app",
        host=_get_bind_host(),
        port=_get_bind_port(),
        reload=True,
        reload_dirs=[os.path.dirname(__file__)],
        log_level="info",
    )

