import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from docx import Document
from openai import OpenAI


DEFAULT_INTERNAL_LLM_URL = ""
DEFAULT_INTERNAL_LLM_MODEL = ""
DEFAULT_INTERNAL_LLM_API_KEY = ""


def settings_base_dir() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def load_saved_llm_settings() -> dict[str, str]:
    settings_path = settings_base_dir() / "app_settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        settings = {}

    return {
        "api_url": str(settings.get("api_url") or os.getenv("INTERNAL_LLM_URL", DEFAULT_INTERNAL_LLM_URL)),
        "api_model": str(settings.get("api_model") or os.getenv("INTERNAL_LLM_MODEL", DEFAULT_INTERNAL_LLM_MODEL)),
        "api_key": str(settings.get("api_key") or os.getenv("INTERNAL_LLM_API_KEY", DEFAULT_INTERNAL_LLM_API_KEY)),
    }


def load_saved_api_url() -> str:
    return load_saved_llm_settings()["api_url"]


def load_saved_api_model() -> str:
    return load_saved_llm_settings()["api_model"]


def load_saved_api_key() -> str:
    return load_saved_llm_settings()["api_key"]


@dataclass(frozen=True)
class LLMConfig:
    api_url: str = field(default_factory=load_saved_api_url)
    model: str = field(default_factory=load_saved_api_model)
    api_key: str = field(default_factory=load_saved_api_key)
    max_tokens: int = int(os.getenv("INTERNAL_LLM_MAX_TOKENS", "3000"))


MEETING_JSON_INSTRUCTION = """
You are an assistant that converts Korean meeting transcripts into a structured meeting-minutes draft.
Return only valid JSON. Do not wrap the answer in markdown.

Required schema:
{
  "title": "meeting title",
  "summary": "brief overall summary",
  "agendas": ["agenda or discussion point"],
  "decisions": ["confirmed decision"],
  "schedules": ["schedule or milestone"],
  "action_items": [
    {"task": "task", "person": "owner", "due_date": "due date or TBD"}
  ],
  "open_issues": ["unresolved issue"]
}
""".strip()


def read_text_file(path: str | Path) -> str:
    path = Path(path)
    for encoding in ("utf-8", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def request_meeting_json(transcript_text: str, config: Optional[LLMConfig] = None) -> dict[str, Any]:
    config = config or LLMConfig()
    client = OpenAI(base_url=config.api_url, api_key=config.api_key)

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": MEETING_JSON_INSTRUCTION},
                {"role": "user", "content": transcript_text},
            ],
            max_tokens=config.max_tokens,
            stream=False,
        )
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        response_obj = getattr(exc, "response", None)
        response_text = getattr(response_obj, "text", "") if response_obj is not None else ""

        detail = f"LLM API request failed: {type(exc).__name__}"
        if status_code:
            detail += f" status={status_code}"
        if response_text:
            detail += f" response={response_text[:500]}"
        detail += f" base_url={config.api_url} model={config.model}"
        raise RuntimeError(detail) from exc

    raw_text = response.choices[0].message.content or ""
    return parse_json_response(raw_text)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    first = raw_text.find("{")
    last = raw_text.rfind("}")
    if first != -1 and last != -1 and first < last:
        return json.loads(raw_text[first : last + 1])

    raise ValueError(f"LLM response is not valid JSON: {raw_text[:500]}")


def add_bullet_list(document: Document, items: list[Any]) -> None:
    if not items:
        document.add_paragraph("-")
        return

    for item in items:
        document.add_paragraph(str(item), style="List Bullet")


def meeting_departments(meeting_info: Optional[dict[str, Any]]) -> str:
    participants = (meeting_info or {}).get("participants") or []
    departments = []
    for participant in participants:
        department = str(participant.get("department") or "").strip()
        if department and department not in departments:
            departments.append(department)
    return ", ".join(departments) if departments else "-"


def meeting_participants_text(meeting_info: Optional[dict[str, Any]]) -> str:
    participants = (meeting_info or {}).get("participants") or []
    lines = []
    for participant in participants:
        department = str(participant.get("department") or "").strip()
        name = str(participant.get("name") or "").strip()
        position = str(participant.get("position") or "").strip()
        parts = [part for part in (department, name, position) if part]
        if parts:
            lines.append(" ".join(parts))
    return ", ".join(lines) if lines else "-"


def add_meeting_metadata(document: Document, meeting_info: Optional[dict[str, Any]]) -> None:
    meeting_info = meeting_info or {}
    table = document.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    rows = [
        ("회의 일자", str(meeting_info.get("generated_at") or "-")),
        ("참여 부서", meeting_departments(meeting_info)),
        ("참여자", meeting_participants_text(meeting_info)),
    ]
    for row, (label, value) in zip(table.rows, rows):
        row.cells[0].text = label
        row.cells[1].text = value
    document.add_paragraph("")


def create_meeting_docx(data: dict[str, Any], output_path: str | Path, meeting_info: Optional[dict[str, Any]] = None) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document()
    document.add_heading(data.get("title") or "회의록 초안", level=1)
    add_meeting_metadata(document, meeting_info)

    document.add_heading("요약", level=2)
    document.add_paragraph(data.get("summary") or "-")

    document.add_heading("주요 안건", level=2)
    add_bullet_list(document, data.get("agendas", []))

    document.add_heading("결정 사항", level=2)
    add_bullet_list(document, data.get("decisions", []))

    document.add_heading("일정", level=2)
    add_bullet_list(document, data.get("schedules", []))

    document.add_heading("Action Items", level=2)
    action_items = data.get("action_items", [])
    if action_items:
        table = document.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        headers = table.rows[0].cells
        headers[0].text = "Task"
        headers[1].text = "Owner"
        headers[2].text = "Due"
        for item in action_items:
            row = table.add_row().cells
            row[0].text = str(item.get("task", ""))
            row[1].text = str(item.get("person", ""))
            row[2].text = str(item.get("due_date", ""))
    else:
        document.add_paragraph("-")

    document.add_heading("미해결 사항", level=2)
    add_bullet_list(document, data.get("open_issues", []))

    document.save(output_path)
    return output_path


def process_transcript_to_docx(
    transcript_path: str | Path,
    docx_path: str | Path,
    json_path: str | Path | None = None,
    config: Optional[LLMConfig] = None,
    meeting_info: Optional[dict[str, Any]] = None,
) -> Path:
    transcript_text = read_text_file(transcript_path)
    data = request_meeting_json(transcript_text, config)

    if json_path:
        json_output = Path(json_path)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return create_meeting_docx(data, docx_path, meeting_info=meeting_info)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert transcript text to meeting-minutes DOCX.")
    parser.add_argument("transcript", help="Input transcript text path.")
    parser.add_argument("--docx", default="outputs/meeting.docx", help="DOCX output path.")
    parser.add_argument("--json", default="outputs/meeting.json", help="JSON output path.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    output = process_transcript_to_docx(args.transcript, args.docx, args.json)
    print(f"Saved DOCX: {output}")
