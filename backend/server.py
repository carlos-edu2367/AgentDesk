"""
Standalone entry point for the AgentDesk backend.
Used by PyInstaller to create the packaged executable.
"""
import os
import sys
import socket
import logging
import logging.handlers
from pathlib import Path


def _get_appdata_log_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / "AgentDesk" / "logs" / "app"
    return Path.home() / ".agentdesk" / "logs" / "app"


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "backend.log"

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _find_free_port(start: int = 8765, end: int = 8900) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def main() -> None:
    _setup_logging(_get_appdata_log_dir())
    logger = logging.getLogger("agentdesk.server")

    is_frozen = getattr(sys, "frozen", False)
    logger.info(f"AgentDesk backend starting (frozen={is_frozen})")

    if is_frozen:
        # PyInstaller sets sys._MEIPASS to the temp extraction directory.
        # We need it on sys.path so 'app' package is importable, and we
        # store it in an env var so run_migrations() can locate alembic files.
        bundle_dir = Path(getattr(sys, "_MEIPASS", ""))
        logger.info(f"Bundle dir: {bundle_dir}")
        if str(bundle_dir) not in sys.path:
            sys.path.insert(0, str(bundle_dir))
        os.environ.setdefault("AGENTDESK_BUNDLE_DIR", str(bundle_dir))

    env_port = os.environ.get("PORT")
    port = int(env_port) if env_port else _find_free_port()
    host = os.environ.get("HOST", "127.0.0.1")

    # Electron parses this line to learn the active port.
    print(f"AGENTDESK_PORT:{port}", flush=True)
    logger.info(f"Starting on {host}:{port}")

    import uvicorn
    from app.main import app as fastapi_app  # noqa: PLC0415

    uvicorn.run(fastapi_app, host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
