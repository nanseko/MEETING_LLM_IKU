import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

# faster-whisper/ctranslate2와 torch 계열 패키지가 함께 설치된 PC에서
# libiomp5md.dll 중복 초기화로 STT 전에 프로세스가 종료되는 것을 막는다.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR.parent


@dataclass(frozen=True)
class AudioPipelineConfig:
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    language: str = os.getenv("WHISPER_LANGUAGE", "ko")
    beam_size: int = int(os.getenv("WHISPER_BEAM_SIZE", "5"))


@dataclass(frozen=True)
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


class SpeakerTurnLike(Protocol):
    start: float
    end: float
    speaker: str


def find_ffmpeg_binary() -> str:
    env_path = os.getenv("FFMPEG_BINARY")
    if env_path:
        ffmpeg_path = Path(env_path)
        if ffmpeg_path.exists():
            return str(ffmpeg_path)
        raise RuntimeError(f"FFMPEG_BINARY is set but the file does not exist: {ffmpeg_path}")

    bundled_candidates = [
        PROJECT_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        PROJECT_DIR / "tools" / "ffmpeg" / "ffmpeg.exe",
        BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe",
    ]
    for candidate in bundled_candidates:
        if candidate.exists():
            return str(candidate)

    path_binary = shutil.which("ffmpeg")
    if path_binary:
        return path_binary

    raise RuntimeError(
        "ffmpeg was not found. Set FFMPEG_BINARY or place ffmpeg.exe at "
        "tools/ffmpeg/bin/ffmpeg.exe."
    )


def run_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg was not found. Set FFMPEG_BINARY or add ffmpeg to PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed: {' '.join(command)}") from exc


def convert_to_wav(input_path: str | Path, wav_path: str | Path) -> Path:
    input_path = Path(input_path)
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        find_ffmpeg_binary(),
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ]
    run_command(command)
    return wav_path


def format_timestamp(seconds: float) -> str:
    total_milliseconds = int(round(seconds * 1000))
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    second = total_seconds % 60
    total_minutes = total_seconds // 60
    minute = total_minutes % 60
    hour = total_minutes // 60
    return f"{hour:02d}:{minute:02d}:{second:02d}.{milliseconds:03d}"


def speaker_for_segment(segment: TranscriptionSegment, speaker_turns: list[SpeakerTurnLike] | None) -> str | None:
    if not speaker_turns:
        return None

    best_speaker = None
    best_overlap = 0.0
    for turn in speaker_turns:
        overlap = max(0.0, min(segment.end, turn.end) - max(segment.start, turn.start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn.speaker

    if best_speaker:
        return best_speaker

    midpoint = (segment.start + segment.end) / 2.0
    for turn in speaker_turns:
        if turn.start <= midpoint <= turn.end:
            return turn.speaker

    nearest = min(
        speaker_turns,
        key=lambda turn: min(abs(segment.start - turn.end), abs(segment.end - turn.start)),
    )
    return nearest.speaker


def write_transcript(segments: Iterable[TranscriptionSegment], transcript_path: str | Path) -> Path:
    transcript_path = Path(transcript_path)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    with transcript_path.open("w", encoding="utf-8") as file:
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            speaker = f"{segment.speaker}: " if segment.speaker else ""
            file.write(f"[{start} - {end}] {speaker}{text}\n")

    return transcript_path


def collect_transcription_segments(raw_segments: Iterable, speaker_turns: list[SpeakerTurnLike] | None = None) -> list[TranscriptionSegment]:
    segments = []
    for raw_segment in raw_segments:
        segment = TranscriptionSegment(
            start=float(raw_segment.start),
            end=float(raw_segment.end),
            text=str(raw_segment.text).strip(),
        )
        if not segment.text:
            continue
        segments.append(
            TranscriptionSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                speaker=speaker_for_segment(segment, speaker_turns),
            )
        )
    return segments


def transcribe_audio(
    wav_path: str | Path,
    transcript_path: str | Path,
    config: AudioPipelineConfig | None = None,
    speaker_turns: list[SpeakerTurnLike] | None = None,
) -> Path:
    from faster_whisper import WhisperModel

    config = config or AudioPipelineConfig()
    model = WhisperModel(
        config.whisper_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
    )
    segments, _ = model.transcribe(
        str(wav_path),
        language=config.language,
        beam_size=config.beam_size,
        vad_filter=True,
    )
    transcript_segments = collect_transcription_segments(segments, speaker_turns)
    return write_transcript(transcript_segments, transcript_path)


def process_recording_file(
    input_path: str | Path,
    transcript_path: str | Path,
    wav_path: str | Path,
    config: AudioPipelineConfig | None = None,
) -> Path:
    wav_output = convert_to_wav(input_path, wav_path)
    return transcribe_audio(wav_output, transcript_path, config)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe an audio file with faster-whisper.")
    parser.add_argument("input", help="Input audio file path.")
    parser.add_argument("--wav", default="outputs/audio.wav", help="Converted 16 kHz mono WAV path.")
    parser.add_argument("--txt", default="outputs/transcript.txt", help="Transcript output path.")
    parser.add_argument("--model", default=None, help="faster-whisper model name. Default: small.")
    parser.add_argument("--device", default=None, help="Device, e.g. cpu or cuda. Default: cpu.")
    parser.add_argument("--compute-type", default=None, help="Compute type. Default: int8.")
    parser.add_argument("--language", default=None, help="Transcription language. Default: ko.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = AudioPipelineConfig(
        whisper_model=args.model or os.getenv("WHISPER_MODEL", "small"),
        whisper_device=args.device or os.getenv("WHISPER_DEVICE", "cpu"),
        whisper_compute_type=args.compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        language=args.language or os.getenv("WHISPER_LANGUAGE", "ko"),
    )
    output = process_recording_file(args.input, args.txt, args.wav, config)
    print(f"Saved transcript: {output}")
