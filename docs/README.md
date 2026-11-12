# 회의록 초안 생성기 (UsingLLM)

녹음 파일이나 브라우저 녹음을 로컬 PC에서 텍스트로 변환하고, 사용자가 지정한 OpenAI 호환 LLM 서버로 회의록 초안 DOCX를 생성하는 Flask 웹 앱입니다.

저장소: [nanseko/MEETING_LLM_IKU](https://github.com/nanseko/MEETING_LLM_IKU). Markdown 문서는 이 `docs/` 폴더에 모았습니다. 아래 명령은 `docs/` 안이 아니라 `launcher.py`가 있는 프로젝트 루트에서 실행합니다.

## 시작하기

처음 사용하는 PC에서는 [INSTALL.md](INSTALL.md)를 따라 Python 패키지, STT 모델, FFmpeg와 LLM 연결을 준비하세요. 설치 후 프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe .\launcher.py
```

브라우저에서 [http://127.0.0.1:5000](http://127.0.0.1:5000)에 접속합니다. 종료는 실행한 터미널에서 `Ctrl+C`입니다.

## 주요 기능

- 음성 파일 업로드와 브라우저 실시간 녹음
- FFmpeg로 16 kHz mono WAV 변환, faster-whisper로 한국어/영어 STT
- tiny/base/small/medium 모델 선택
- 선택형 화자 분리: pyannote 기반 Speaker-Diarization
- 회의 정보와 STT 후처리 규칙을 반영한 LLM 회의록 생성
- DOCX 다운로드와 변환 기록 조회·검색

## 포함 파일

```text
docs/
  README.md                       프로젝트 안내
  INSTALL.md                      설치와 설정
  USAGE.md                        사용 방법
  stt_correction_rules.md          실행 시 읽는 STT 후처리 규칙
  ...                             오프라인·화자 분리·exe 빌드 문서
source/
  __init__.py
  app.py                         웹 라우트·설정·진행 상태·기록
  audio_pipeline.py              FFmpeg 변환과 STT
  diarization_service.py         선택형 화자 분리
  meeting_minutes_service.py     LLM 호출과 DOCX 생성
  job_runner.py                  백그라운드 작업 실행
  app_settings.example.json      비밀정보 없는 설정 예시
  templates/app.html
  static/{styles.css,home.js,settings.js}
launcher.py                      프로젝트 루트에서 실행
download_model.py                STT 모델 4종 다운로드
requirements.txt                기본 실행 패키지
requirements-diarization.txt    선택형 화자 분리 패키지
requirements-build.txt          선택형 Windows exe 빌드 패키지
MeetingMinutesApp.spec          PyInstaller 구성
build_exe.ps1                   기존 Windows 빌드 도우미
```

## 문서

| 문서 | 내용 |
| --- | --- |
| [INSTALL.md](INSTALL.md) | 다른 PC에서 처음 설치·설정·실행 |
| [USAGE.md](USAGE.md) | 화면 사용법과 문제 해결 |
| [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md) | 인터넷 없는 PC용 패키지 준비 |
| [FFMPEG_OFFLINE.md](FFMPEG_OFFLINE.md) | FFmpeg 다운로드와 경로 설정 |
| [SPEAKER_DIARIZATION.md](SPEAKER_DIARIZATION.md) | 선택형 화자 분리 설치와 모델 |
| [EXE_BUILD.md](EXE_BUILD.md) | Windows exe 빌드와 배포 |
| [GIT_UPLOAD.md](GIT_UPLOAD.md) | GitHub에 올릴 범위와 준비 사항 |
| [EXPORT_NOTES.md](EXPORT_NOTES.md) | 포함·제외 기준과 검증 범위 |
| [UPLOAD_MANIFEST.txt](../UPLOAD_MANIFEST.txt) | 배포 파일별 SHA-256 목록 |

## 별도로 준비할 항목

이 저장소는 소스 배포본입니다. `models/`, `tools/`, `wheelhouse*/`, 가상환경과 실행 결과는 포함하지 않습니다. 모델과 FFmpeg를 설치 안내에 따라 준비해야 음성 처리가 가능합니다. LLM API URL·모델명·키도 직접 설정해야 하며, 사내 서버를 사용하면 해당 서버에 접근할 수 있는 네트워크가 필요합니다.

STT는 로컬에서 처리하지만, LLM 요약 단계에서는 회의 텍스트와 입력한 회의 정보가 설정한 서버로 전송됩니다. 기본 실행 환경은 Windows x64 / Python 3.12 / CPU입니다. 다른 OS에서의 실행은 별도 검증하지 않았습니다.
