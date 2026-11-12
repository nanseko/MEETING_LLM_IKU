import json
import os
import re
import shutil
import subprocess
import sys
import wave
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

try:
    from .audio_pipeline import AudioPipelineConfig, convert_to_wav, transcribe_audio
    from .diarization_service import DiarizationConfig, diarization_status, diarize_audio
    from .meeting_minutes_service import LLMConfig, process_transcript_to_docx
except ImportError:
    from audio_pipeline import AudioPipelineConfig, convert_to_wav, transcribe_audio
    from diarization_service import DiarizationConfig, diarization_status, diarize_audio
    from meeting_minutes_service import LLMConfig, process_transcript_to_docx


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
HISTORY_PATH = BASE_DIR / "conversion_history.json"
SETTINGS_PATH = BASE_DIR / "app_settings.json"
STT_CORRECTION_RULES_NAME = "stt_correction_rules.md"
ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".webm"}
MODEL_NAMES = {"tiny", "base", "small", "medium"}
LANGUAGE_NAMES = {"ko": "한국어", "en": "영어"}
DEFAULT_API_KEY = os.getenv("INTERNAL_LLM_API_KEY", "")
DEFAULT_API_URL = os.getenv("INTERNAL_LLM_URL", "")
DEFAULT_API_MODEL = os.getenv("INTERNAL_LLM_MODEL", "")
DEFAULT_SETTINGS = {
    "api_url": DEFAULT_API_URL,
    "api_model": DEFAULT_API_MODEL,
    "api_key": DEFAULT_API_KEY,
    "stt_model": "small",
    "speaker_diarization": False,
    "recording_dir": str(UPLOAD_DIR),
    "secure_business": False,
}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
PROGRESS_LOGS: dict[str, dict] = {}
JOB_RESULTS: dict[str, dict] = {}
PROGRESS_LOCK = Lock()


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def read_json_file(path: Path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def write_json_file(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def progress_file_path(job_id: str) -> Path:
    return OUTPUT_DIR / job_id / "progress.json"


def result_file_path(job_id: str) -> Path:
    return OUTPUT_DIR / job_id / "result.json"


def read_progress_file(job_id: str) -> dict | None:
    return read_json_file(progress_file_path(job_id), None)


def read_result_file(job_id: str) -> dict:
    return read_json_file(result_file_path(job_id), {})


def write_progress_file(job_id: str, progress: dict) -> None:
    path = progress_file_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, progress)


def write_result_file(job_id: str, result: dict) -> None:
    path = result_file_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file(path, result)


def update_progress(job_id: str, message: str, state: str = "running", detail: str | None = None) -> None:
    if not job_id:
        return

    event = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "state": state,
    }
    if detail:
        event["detail"] = detail

    with PROGRESS_LOCK:
        progress = PROGRESS_LOGS.get(job_id) or read_progress_file(job_id)
        if not progress:
            progress = {"job_id": job_id, "state": "running", "events": [], "updated_at": datetime.now().isoformat()}
        PROGRESS_LOGS[job_id] = progress
        progress["state"] = state
        progress["updated_at"] = datetime.now().isoformat()
        progress["events"].append(event)
        progress["events"] = progress["events"][-120:]
        write_progress_file(job_id, progress)


def set_job_result(job_id: str, **data) -> None:
    with PROGRESS_LOCK:
        current = JOB_RESULTS.get(job_id) or read_result_file(job_id)
        JOB_RESULTS[job_id] = current
        current.update(data)
        write_result_file(job_id, current)


def get_progress(job_id: str) -> dict:
    with PROGRESS_LOCK:
        progress = read_progress_file(job_id) or PROGRESS_LOGS.get(job_id)
        result = read_result_file(job_id) or dict(JOB_RESULTS.get(job_id, {}))
        if not progress:
            payload = {"job_id": job_id, "state": result.get("state", "idle"), "events": []}
        else:
            payload = {
                "job_id": progress["job_id"],
                "state": progress["state"],
                "events": list(progress["events"]),
                "updated_at": progress["updated_at"],
            }

    if result.get("state") == "complete":
        payload["download_url"] = url_for("download_result", job_id=job_id)
        if result.get("secure_business"):
            payload["cleanup_url"] = url_for("cleanup_result", job_id=job_id)
    if result.get("error"):
        payload["error"] = result["error"]
    return payload


def load_history() -> list[dict]:
    return read_json_file(HISTORY_PATH, [])


def save_history(entries: list[dict]) -> None:
    write_json_file(HISTORY_PATH, entries)


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    saved_settings = read_json_file(SETTINGS_PATH, {})
    for key in DEFAULT_SETTINGS:
        if key in saved_settings:
            settings[key] = saved_settings[key]

    if settings["stt_model"] not in MODEL_NAMES:
        settings["stt_model"] = "small"
    settings["speaker_diarization"] = bool(settings.get("speaker_diarization"))
    settings["secure_business"] = bool(settings.get("secure_business"))
    settings["recording_dir"] = str(settings.get("recording_dir") or UPLOAD_DIR)
    settings["api_url"] = str(settings.get("api_url") or DEFAULT_API_URL)
    settings["api_model"] = str(settings.get("api_model") or DEFAULT_API_MODEL)
    settings["api_key"] = str(settings.get("api_key") or DEFAULT_API_KEY)
    return settings


def save_settings(settings: dict) -> None:
    write_json_file(SETTINGS_PATH, settings)


def recording_root_dir(settings: dict) -> Path:
    path = Path(settings.get("recording_dir") or UPLOAD_DIR).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def add_history_entry(entry: dict) -> None:
    entries = load_history()
    entries.insert(0, entry)
    save_history(entries)


def read_meeting_title(json_path: Path, fallback: str) -> str:
    data = read_json_file(json_path, {})
    title = str(data.get("title") or "").strip()
    return title or fallback


def wav_duration_seconds(wav_path: Path) -> float:
    try:
        with wave.open(str(wav_path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            return frames / float(rate) if rate else 0.0
    except (wave.Error, OSError):
        return 0.0


def format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def filter_history(entries: list[dict], filters: dict[str, str]) -> list[dict]:
    query = filters.get("q", "").strip().lower()
    start = filters.get("start", "").strip()
    end = filters.get("end", "").strip()
    user = filters.get("user", "").strip()
    filtered = []

    for entry in entries:
        title = str(entry.get("title", "")).lower()
        file_name = str(entry.get("file_name", "")).lower()
        generated_date = str(entry.get("generated_at", ""))[:10]
        entry_user = str(entry.get("user_id", ""))

        if query and query not in title and query not in file_name:
            continue
        if start and generated_date < start:
            continue
        if end and generated_date > end:
            continue
        if user and entry_user != user:
            continue
        filtered.append(entry)

    return filtered


def validate_whisper_model_dir(model_dir: Path) -> list[str]:
    missing = [
        name
        for name in ("model.bin", "config.json", "tokenizer.json")
        if not (model_dir / name).exists()
    ]
    if not list(model_dir.glob("vocabulary.*")):
        missing.append("vocabulary.*")
    return missing


def resolve_whisper_model(model_name: str | None = None) -> str:
    selected_model = model_name if model_name in MODEL_NAMES else load_settings()["stt_model"]
    invalid_candidates = []
    for model_dir in (
        BASE_DIR.parent / "models" / f"faster-whisper-{selected_model}",
        BASE_DIR / "models" / f"faster-whisper-{selected_model}",
    ):
        if model_dir.exists():
            missing = validate_whisper_model_dir(model_dir)
            if missing:
                invalid_candidates.append(f"{model_dir} (누락: {', '.join(missing)})")
                continue
            return str(model_dir)

    if invalid_candidates:
        raise RuntimeError(
            f"STT 모델 '{selected_model}' 폴더가 불완전합니다. "
            f"{'; '.join(invalid_candidates)}. "
            "외부망 PC에서 Systran/faster-whisper 모델 전체를 다시 다운로드한 뒤 "
            f"models/faster-whisper-{selected_model} 폴더로 복사해 주세요."
        )

    raise RuntimeError(
        f"Selected model '{selected_model}' was not found. "
        f"Place it at models/faster-whisper-{selected_model}."
    )


def sanitize_download_stem(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", value).strip().strip(".")
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "회의록"


def parse_participant_count(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    if not value.isdigit():
        raise ValueError("인원수는 숫자만 입력할 수 있습니다.")
    count = int(value)
    if count < 1 or count > 99:
        raise ValueError("인원수는 1 이상 99 이하로 입력해 주세요.")
    return count


def parse_meeting_info(form) -> dict:
    title = str(form.get("meeting_title", "")).strip() or "회의록"
    participant_count = parse_participant_count(str(form.get("participant_count", "")))
    language = str(form.get("meeting_language", "ko")).lower()
    if language not in LANGUAGE_NAMES:
        language = "ko"
    secure_business = str(form.get("secure_business", "")).lower() in {"1", "true", "on", "yes"}
    return {
        "title": title,
        "participants": parse_participants(str(form.get("participants_json", "[]"))),
        "participant_count": participant_count,
        "language": language,
        "secure_business": secure_business,
    }


def parse_participants(raw_json: str) -> list[dict[str, str]]:
    try:
        raw_items = json.loads(raw_json or "[]")
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_items, list):
        return []

    participants = []
    for item in raw_items[:99]:
        if not isinstance(item, dict):
            continue
        participant = {
            "department": str(item.get("department") or "").strip()[:80],
            "position": str(item.get("position") or "").strip()[:40],
            "name": str(item.get("name") or "").strip()[:40],
        }
        if participant["department"] or participant["position"] or participant["name"]:
            participants.append(participant)
    return participants


def write_llm_transcript_with_context(transcript_path: Path, output_path: Path, meeting_info: dict) -> Path:
    transcript_text = transcript_path.read_text(encoding="utf-8")
    correction_rules = load_stt_correction_rules()
    context_lines = [
        "[회의 정보]",
        f"회의명: {meeting_info['title']}",
        f"사용언어: {LANGUAGE_NAMES[meeting_info['language']]}",
    ]
    if meeting_info.get("participant_count"):
        context_lines.append(f"인원수: {meeting_info['participant_count']}명")
    if meeting_info.get("participants"):
        context_lines.extend(["", "[주요 참여 인원]"])
        for index, participant in enumerate(meeting_info["participants"], start=1):
            context_lines.append(
                f"{index}. 부서명: {participant.get('department') or '-'} / "
                f"직급: {participant.get('position') or '-'} / "
                f"이름: {participant.get('name') or '-'}"
            )
    if correction_rules:
        context_lines.extend(
            [
                "",
                "[STT 후처리 및 회의록 작성 규칙]",
                correction_rules,
            ]
        )
    context_lines.extend(["", "[회의 음성 Transcript]", transcript_text])
    output_path.write_text("\n".join(context_lines), encoding="utf-8")
    return output_path


def load_stt_correction_rules() -> str:
    candidates = [
        BASE_DIR / "docs" / STT_CORRECTION_RULES_NAME,
        Path(__file__).resolve().parent.parent / "docs" / STT_CORRECTION_RULES_NAME,
        BASE_DIR / "_internal" / "docs" / STT_CORRECTION_RULES_NAME,
        BASE_DIR / STT_CORRECTION_RULES_NAME,
        BASE_DIR / "source" / STT_CORRECTION_RULES_NAME,
        BASE_DIR / "_internal" / "source" / STT_CORRECTION_RULES_NAME,
        Path(__file__).resolve().parent / STT_CORRECTION_RULES_NAME,
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return ""


def render_page(page: str, **context):
    return render_template("app.html", page=page, **context)


def get_diarization_context() -> dict:
    try:
        status = diarization_status()
    except Exception as exc:
        return {"ready": False, "message": str(exc)}
    return {"ready": True, "message": "Speaker-Diarization is ready.", **status}


def json_error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def process_upload_job(
    job_id: str,
    input_path: Path,
    filename: str,
    settings: dict,
    meeting_info: dict,
    job_upload_dir: Path,
    job_output_dir: Path,
) -> None:
    wav_path = job_output_dir / "audio.wav"
    transcript_path = job_output_dir / "transcript.txt"
    llm_transcript_path = job_output_dir / "transcript_for_llm.txt"
    json_path = job_output_dir / "meeting.json"
    selected_model = settings["stt_model"]
    language = meeting_info["language"]
    meeting_title = meeting_info["title"]
    participant_count = meeting_info["participant_count"]
    generated_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    download_name = f"{sanitize_download_stem(meeting_title)}_{generated_stamp}.docx"
    docx_path = job_output_dir / download_name

    try:
        app.logger.info("Job %s: preprocessing started", job_id)
        update_progress(
            job_id,
            f"전처리를 시작했습니다. STT 모델: {selected_model}, 언어: {LANGUAGE_NAMES[language]}",
        )
        if participant_count:
            update_progress(job_id, f"회의 인원수 입력값을 확인했습니다: {participant_count}명")

        whisper_model_path = resolve_whisper_model(selected_model)
        update_progress(job_id, "STT 모델 파일 확인 완료", detail=whisper_model_path)
        audio_config = AudioPipelineConfig(
            whisper_model=whisper_model_path,
            language=language,
        )
        llm_config = LLMConfig()

        update_progress(job_id, "ffmpeg로 16 kHz mono WAV 변환 중입니다.")
        wav_output = convert_to_wav(input_path, wav_path)
        update_progress(job_id, "WAV 변환 완료", detail=str(wav_output))

        speaker_turns = None
        if settings.get("speaker_diarization"):
            app.logger.info("Job %s: speaker diarization started", job_id)
            update_progress(job_id, "Speaker-Diarization 화자 분리 분석 중입니다.")
            diarization_config = DiarizationConfig(
                min_speakers=participant_count,
                max_speakers=participant_count,
            )
            speaker_turns = diarize_audio(wav_output, job_output_dir, diarization_config)
            speaker_count = len({turn.speaker for turn in speaker_turns})
            update_progress(job_id, f"화자 분리 완료: {speaker_count}명 추정")

        update_progress(job_id, "faster-whisper STT 분석 중입니다.")
        transcribe_audio(wav_output, transcript_path, audio_config, speaker_turns=speaker_turns)
        debug_transcript_path = OUTPUT_DIR / f"{generated_stamp}_{job_id[:8]}_transcript.txt"
        shutil.copy2(transcript_path, debug_transcript_path)
        update_progress(
            job_id,
            "transcript.txt 생성 완료",
            detail=f"{transcript_path} / 디버그 사본: {debug_transcript_path}",
        )

        app.logger.info("Job %s: LLM/DOCX processing started", job_id)
        update_progress(job_id, "전처리 완료. 사내 LLM API 호출 단계로 진입합니다.")
        write_llm_transcript_with_context(transcript_path, llm_transcript_path, meeting_info)
        meeting_info["generated_at"] = datetime.now().strftime("%Y-%m-%d")
        process_transcript_to_docx(llm_transcript_path, docx_path, json_path, llm_config, meeting_info=meeting_info)

        title = read_meeting_title(json_path, meeting_title)
        add_history_entry(
            {
                "job_id": job_id,
                "user_id": os.getenv("APP_USER_ID", "local"),
                "title": title,
                "file_name": filename,
                "meeting_title": meeting_title,
                "participant_count": participant_count or "",
                "participants": meeting_info.get("participants", []),
                "language": language,
                "model": selected_model,
                "speaker_diarization": bool(settings.get("speaker_diarization")),
                "duration": format_duration(wav_duration_seconds(wav_path)),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "docx_path": str(docx_path),
            }
        )

        if meeting_info.get("secure_business"):
            shutil.rmtree(job_upload_dir, ignore_errors=True)
            update_progress(job_id, "보안 사업 옵션에 따라 임시 업로드 파일을 삭제했습니다.")

        set_job_result(
            job_id,
            state="complete",
            docx_path=str(docx_path),
            download_name=download_name,
            secure_business=bool(meeting_info.get("secure_business")),
            job_output_dir=str(job_output_dir),
        )
        update_progress(job_id, "DOCX 생성 완료", "complete", str(docx_path))
    except Exception as exc:
        app.logger.exception("Job %s failed", job_id)
        error_message = f"{type(exc).__name__}: {exc}"
        update_progress(job_id, "오류가 발생했습니다.", "error", error_message)
        set_job_result(job_id, state="error", error=error_message)


def runner_command(config_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--job-runner", str(config_path)]
    return [sys.executable, str(BASE_DIR / "job_runner.py"), str(config_path)]


def monitor_job_process(job_id: str, config_path: Path, log_path: Path) -> None:
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                runner_command(config_path),
                cwd=str(BASE_DIR.parent if not getattr(sys, "frozen", False) else BASE_DIR),
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            return_code = process.wait()
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        update_progress(job_id, "작업 프로세스를 실행하지 못했습니다.", "error", error_message)
        set_job_result(job_id, state="error", error=error_message)
        return

    latest = read_result_file(job_id)
    if return_code != 0 and latest.get("state") != "error":
        error_message = f"작업 프로세스가 비정상 종료되었습니다. exit_code={return_code}, log={log_path}"
        update_progress(job_id, "작업 프로세스가 비정상 종료되었습니다.", "error", error_message)
        set_job_result(job_id, state="error", error=error_message)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return upload()
    return render_page("home", settings=load_settings())


@app.route("/history", methods=["GET"])
def history():
    filters = {
        "q": request.args.get("q", ""),
        "start": request.args.get("start", ""),
        "end": request.args.get("end", ""),
        "user": request.args.get("user", ""),
    }
    entries = load_history()
    user_ids = sorted({str(entry.get("user_id", "local")) for entry in entries})
    return render_page(
        "history",
        filters=filters,
        history_entries=filter_history(entries, filters),
        user_ids=user_ids,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    current_settings = load_settings()
    if request.method == "POST":
        selected_model = request.form.get("stt_model", "small")
        current_settings.update(
            {
                "api_url": request.form.get("api_url", "").strip() or DEFAULT_API_URL,
                "api_model": request.form.get("api_model", "").strip() or DEFAULT_API_MODEL,
                "api_key": request.form.get("api_key", "").strip() or DEFAULT_API_KEY,
                "stt_model": selected_model if selected_model in MODEL_NAMES else "small",
                "speaker_diarization": request.form.get("speaker_diarization") == "on",
                "recording_dir": request.form.get("recording_dir", "").strip() or str(UPLOAD_DIR),
            }
        )
        save_settings(current_settings)
        flash("설정이 저장되었습니다.")
        return redirect(url_for("settings"))

    return render_page("settings", settings=current_settings, diarization=get_diarization_context())


@app.route("/history/<job_id>/delete", methods=["POST"])
def delete_history(job_id: str):
    entries = [entry for entry in load_history() if entry.get("job_id") != job_id]
    save_history(entries)
    return redirect(url_for("history", **request.args))


@app.route("/progress/<job_id>", methods=["GET"])
def progress(job_id: str):
    return jsonify(get_progress(job_id))


@app.route("/download/<job_id>", methods=["GET"])
def download_result(job_id: str):
    with PROGRESS_LOCK:
        result = dict(JOB_RESULTS.get(job_id, {}))

    if result.get("state") != "complete":
        return json_error("DOCX 파일이 아직 생성되지 않았습니다.", 404)

    docx_path = Path(result.get("docx_path", ""))
    if not docx_path.exists():
        return json_error("생성된 DOCX 파일을 찾을 수 없습니다.", 404)

    return send_file(
        docx_path,
        as_attachment=True,
        download_name=result.get("download_name") or f"meeting_minutes_{job_id[:8]}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/cleanup/<job_id>", methods=["POST"])
def cleanup_result(job_id: str):
    result = read_result_file(job_id) or dict(JOB_RESULTS.get(job_id, {}))
    if not result.get("secure_business"):
        return jsonify({"status": "skipped"})

    output_dir = Path(result.get("job_output_dir") or OUTPUT_DIR / job_id).resolve()
    allowed_root = OUTPUT_DIR.resolve()
    if output_dir == allowed_root or allowed_root not in output_dir.parents:
        return json_error("정리 대상 경로가 올바르지 않습니다.", 400)

    shutil.rmtree(output_dir, ignore_errors=True)
    with PROGRESS_LOCK:
        PROGRESS_LOGS.pop(job_id, None)
        JOB_RESULTS.pop(job_id, None)
    return jsonify({"status": "deleted"})


@app.route("/upload", methods=["POST"])
def upload():
    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        return json_error("업로드할 음성 파일을 선택해 주세요.")

    if not is_allowed_file(uploaded_file.filename):
        return json_error("지원하지 않는 파일 형식입니다.")

    try:
        meeting_info = parse_meeting_info(request.form)
    except ValueError as exc:
        return json_error(str(exc))

    settings = load_settings()
    requested_job_id = request.form.get("job_id", "").strip()
    job_id = requested_job_id if requested_job_id else uuid4().hex

    job_upload_dir = recording_root_dir(settings) / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(uploaded_file.filename) or f"recording_{job_id}.webm"
    input_path = job_upload_dir / filename

    set_job_result(job_id, state="running")
    update_progress(job_id, "작업을 시작했습니다.")
    update_progress(job_id, "업로드 파일을 로컬 임시 저장소에 저장하는 중입니다.")
    uploaded_file.save(input_path)
    update_progress(job_id, "업로드 파일 저장 완료", detail=str(input_path))

    job_config_path = job_output_dir / "job_config.json"
    job_log_path = job_output_dir / "job_process.log"
    write_json_file(
        job_config_path,
        {
            "job_id": job_id,
            "input_path": str(input_path),
            "filename": filename,
            "settings": settings,
            "meeting_info": meeting_info,
            "job_upload_dir": str(job_upload_dir),
            "job_output_dir": str(job_output_dir),
        },
    )

    worker = Thread(
        target=monitor_job_process,
        args=(job_id, job_config_path, job_log_path),
        daemon=True,
    )
    worker.start()

    return jsonify({"job_id": job_id, "state": "accepted"}), 202


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--job-runner":
        try:
            from .job_runner import run_from_config
        except ImportError:
            from job_runner import run_from_config

        run_from_config(sys.argv[2])
        raise SystemExit(0)

    app.run(
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
    )
