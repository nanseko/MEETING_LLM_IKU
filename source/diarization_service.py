import os
import shutil
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR.parent

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


@dataclass(frozen=True)
class DiarizationConfig:
    device: str = os.getenv("PYANNOTE_DEVICE", "cpu")
    min_speakers: int | None = None
    max_speakers: int | None = None


def _model_dir(*names: str) -> Path:
    candidates = []
    for name in names:
        candidates.extend(
            [
                PROJECT_DIR / "models" / name,
                BASE_DIR.parent / "models" / name,
                BASE_DIR / "models" / name,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _required_model_paths() -> dict[str, Path]:
    return {
        "pipeline": _model_dir(
            "speaker-diarization-3.1",
            "pyannote-speaker-diarization-3.1",
        ),
        "segmentation": _model_dir(
            "segmentation-3.0",
            "pyannote-segmentation-3.0",
        ),
        "embedding": _model_dir(
            "wespeaker-voxceleb-resnet34-LM",
            "pyannote-wespeaker-voxceleb-resnet34-LM",
        ),
    }


def optional_model_paths() -> dict[str, Path]:
    return {
        "voice_activity_detection": _model_dir(
            "voice-activity-detection",
            "pyannote-voice-activity-detection",
        )
    }


def validate_diarization_assets() -> dict[str, Path]:
    paths = _required_model_paths()
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        detail = "\n".join(missing)
        raise RuntimeError(
            "Speaker-Diarization model files are missing. "
            "Download these model folders under models/ first:\n"
            f"{detail}"
        )

    config_path = paths["pipeline"] / "config.yaml"
    if not config_path.exists():
        raise RuntimeError(f"pyannote pipeline config was not found: {config_path}")

    for name, path in paths.items():
        if name == "pipeline":
            continue
        if not (path / "config.yaml").exists():
            raise RuntimeError(f"pyannote {name} config was not found: {path / 'config.yaml'}")
        if not (path / "pytorch_model.bin").exists():
            raise RuntimeError(f"pyannote {name} checkpoint was not found: {path / 'pytorch_model.bin'}")

    return paths


def _neutral_checkpoint_alias(checkpoint: Path, alias_name: str) -> Path:
    alias_dir = PROJECT_DIR / "outputs" / "_model_links"
    alias_dir.mkdir(parents=True, exist_ok=True)
    alias = alias_dir / alias_name
    if alias.exists() and alias.stat().st_size == checkpoint.stat().st_size:
        return alias
    if alias.exists():
        alias.unlink()

    try:
        os.link(checkpoint, alias)
    except OSError:
        shutil.copy2(checkpoint, alias)
    return alias


def _write_local_pipeline_config(paths: dict[str, Path], work_dir: Path) -> Path:
    source_config = paths["pipeline"] / "config.yaml"
    config_text = source_config.read_text(encoding="utf-8")
    segmentation_checkpoint = paths["segmentation"] / "pytorch_model.bin"
    embedding_checkpoint = _neutral_checkpoint_alias(
        paths["embedding"] / "pytorch_model.bin",
        "embedding_model.bin",
    )
    config_text = config_text.replace(
        "segmentation: pyannote/segmentation-3.0",
        f"segmentation: {segmentation_checkpoint.as_posix()}",
    )
    config_text = config_text.replace(
        "embedding: pyannote/wespeaker-voxceleb-resnet34-LM",
        f"embedding: {embedding_checkpoint.as_posix()}",
    )

    work_dir.mkdir(parents=True, exist_ok=True)
    local_config = work_dir / "pyannote_local_config.yaml"
    local_config.write_text(config_text, encoding="utf-8")
    return local_config


@contextmanager
def _without_inspect_stack():
    import inspect

    original_stack = inspect.stack
    inspect.stack = lambda context=1: []
    try:
        yield
    finally:
        inspect.stack = original_stack


def diarization_status() -> dict[str, str | bool]:
    required = validate_diarization_assets()
    optional = optional_model_paths()
    return {
        "ready": True,
        "pipeline": str(required["pipeline"]),
        "segmentation": str(required["segmentation"]),
        "embedding": str(required["embedding"]),
        "voice_activity_detection": str(optional["voice_activity_detection"])
        if optional["voice_activity_detection"].exists()
        else "",
    }


def validate_pyannote_runtime() -> None:
    try:
        pyannote_version = version("pyannote.audio")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "Speaker-Diarization is ON, but pyannote.audio is not installed. "
            "Install the optional packages from requirements-diarization.txt."
        ) from exc

    major_text = pyannote_version.split(".", 1)[0]
    major = int(major_text) if major_text.isdigit() else 0
    if major >= 4:
        raise RuntimeError(
            "pyannote.audio 4.x is installed, but this local offline setup uses "
            "pyannote/speaker-diarization-3.1. Install pyannote.audio==3.3.0 "
            "in the Web UI environment."
        )


def _normalize_speaker_labels(turns: list[SpeakerTurn]) -> list[SpeakerTurn]:
    label_map: dict[str, str] = {}
    normalized = []
    for turn in sorted(turns, key=lambda item: (item.start, item.end)):
        if turn.speaker not in label_map:
            label_map[turn.speaker] = f"Speaker {len(label_map) + 1}"
        normalized.append(
            SpeakerTurn(
                start=turn.start,
                end=turn.end,
                speaker=label_map[turn.speaker],
            )
        )
    return normalized


def diarize_audio(
    wav_path: str | Path,
    work_dir: str | Path,
    config: DiarizationConfig | None = None,
) -> list[SpeakerTurn]:
    validate_pyannote_runtime()

    warnings.filterwarnings(
        "ignore",
        message="Module 'speechbrain.pretrained' was deprecated.*",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Speaker-Diarization is ON, but pyannote.audio/torch is not installed. "
            "Install pyannote.audio, torch, and torchaudio in the current environment."
        ) from exc

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "0")

    config = config or DiarizationConfig()
    paths = validate_diarization_assets()
    local_config = _write_local_pipeline_config(paths, Path(work_dir))

    with _without_inspect_stack():
        pipeline = Pipeline.from_pretrained(str(local_config))
    if hasattr(pipeline, "to"):
        pipeline.to(torch.device(config.device))

    kwargs = {}
    if config.min_speakers:
        kwargs["min_speakers"] = config.min_speakers
    if config.max_speakers:
        kwargs["max_speakers"] = config.max_speakers

    diarization = pipeline(str(wav_path), **kwargs)
    turns = [
        SpeakerTurn(
            start=float(segment.start),
            end=float(segment.end),
            speaker=str(label),
        )
        for segment, _, label in diarization.itertracks(yield_label=True)
    ]
    return _normalize_speaker_labels(turns)


def assign_speaker(start: float, end: float, turns: list[SpeakerTurn]) -> str | None:
    if not turns:
        return None

    best_speaker = None
    best_overlap = 0.0
    for turn in turns:
        overlap = max(0.0, min(end, turn.end) - max(start, turn.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn.speaker

    if best_speaker:
        return best_speaker

    midpoint = (start + end) / 2.0
    for turn in turns:
        if turn.start <= midpoint <= turn.end:
            return turn.speaker

    nearest = min(turns, key=lambda turn: min(abs(start - turn.end), abs(end - turn.start)))
    return nearest.speaker
