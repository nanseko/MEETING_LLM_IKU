# Windows exe 빌드

exe는 선택 사항입니다. Python으로 실행하는 데는 필요하지 않습니다. 아래 명령은 프로젝트 루트, Windows x64 / Python 3.12 가상환경 기준입니다.

## 기본 빌드

[INSTALL.md](INSTALL.md)에 따라 가상환경과 기본 패키지를 준비한 뒤 빌드 도구를 추가합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\MeetingMinutesApp.spec
```

생성 위치는 `dist/MeetingMinutesApp/MeetingMinutesApp.exe`입니다. 화자 분리를 포함하려면 빌드 전에 `requirements-diarization.txt`도 같은 가상환경에 설치합니다.

모델과 FFmpeg는 PyInstaller spec에 포함되지 않으므로 생성된 exe 옆에 별도로 복사합니다.

```text
dist/MeetingMinutesApp/
  MeetingMinutesApp.exe
  _internal/
  models/faster-whisper-small/...
  tools/ffmpeg/bin/ffmpeg.exe
```

STT 보정 규칙 `docs/stt_correction_rules.md`는 spec에 따라 `_internal/docs/`에 포함됩니다. 배포 후 규칙을 직접 편집하려면 exe 옆 `docs/stt_correction_rules.md`에 두면 이 파일을 우선 사용합니다.

다른 STT 모델과 화자 분리를 사용하면 해당 모델 폴더도 함께 둡니다. PC에 따라 Microsoft VC++ x64 런타임이 필요합니다. 파일 하나만 옮기지 말고 `MeetingMinutesApp` 폴더 전체를 배포합니다.

## 실행

```powershell
.\dist\MeetingMinutesApp\MeetingMinutesApp.exe
```

브라우저에서 [http://127.0.0.1:5000](http://127.0.0.1:5000)에 접속합니다. 자동으로 브라우저를 열려면 실행 전에 `$env:OPEN_BROWSER = '1'`을 지정합니다. 실행을 종료하려면 터미널에서 `Ctrl+C`를 누릅니다.

LLM 연결 정보는 처음 실행한 뒤 설정 화면에 입력합니다. 실제 설정과 업로드·결과 폴더는 exe 옆에 생성됩니다. 배포용으로 빌드할 때 기존 사용자의 설정이나 녹음을 함께 복사하지 마세요.

## 기존 build_exe.ps1

빌드 도우미도 함께 포함했습니다. 이 스크립트는 기존 `build/`, `dist/`를 비우고, 화자 분리 패키지까지 설치한 후 `models/`, `tools/`, `docs/`를 배포 폴더로 복사합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

기본 기능만 빌드하려면 위의 수동 PyInstaller 명령을 사용합니다. 원본 도우미에는 pip 온라인 업그레이드 단계가 있으므로 폐쇄망에서는 아래 절차를 사용합니다.

## 폐쇄망 빌드

인터넷 PC에서 빌드 도구 wheel을 기본 wheelhouse에 추가합니다.

```powershell
.\.venv-download\Scripts\python.exe -m pip download --only-binary=:all: -r .\requirements-build.txt -d .\wheelhouse
```

대상 PC에서는 준비된 가상환경에 로컬 설치 후 빌드합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\requirements-build.txt
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\MeetingMinutesApp.spec
```

exe 빌드 및 다른 PC에서의 실제 추론은 이번 소스 정리 과정에서 수행하지 않았습니다.
