import json
import sys
from pathlib import Path

try:
    from .app import process_upload_job
except ImportError:
    from app import process_upload_job


def run_from_config(config_path: str | Path) -> None:
    config_path = Path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    process_upload_job(
        config["job_id"],
        Path(config["input_path"]),
        config["filename"],
        config["settings"],
        config["meeting_info"],
        Path(config["job_upload_dir"]),
        Path(config["job_output_dir"]),
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python source/job_runner.py <job_config.json>")
    run_from_config(sys.argv[1])
