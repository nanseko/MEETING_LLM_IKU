import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from source.app import app
from source.job_runner import run_from_config


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_local_resources(base_dir: Path) -> None:
    model_dir = base_dir / "models" / "faster-whisper-small"
    ffmpeg_path = base_dir / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"

    if model_dir.exists():
        os.environ.setdefault("WHISPER_MODEL", str(model_dir))
    os.environ.setdefault("WHISPER_DEVICE", "cpu")
    os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")
    os.environ.setdefault("WHISPER_LANGUAGE", "ko")

    if ffmpeg_path.exists():
        os.environ.setdefault("FFMPEG_BINARY", str(ffmpeg_path))


def open_browser(host: str, port: int) -> None:
    time.sleep(1.2)
    browser_host = "localhost" if host in {"127.0.0.1", "0.0.0.0"} else host
    webbrowser.open(f"http://{browser_host}:{port}")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--job-runner":
        run_from_config(sys.argv[2])
        return

    base_dir = runtime_dir()
    configure_local_resources(base_dir)

    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))

    if os.getenv("OPEN_BROWSER", "0") == "1":
        threading.Thread(target=open_browser, args=(host, port), daemon=True).start()

    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
