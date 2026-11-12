# 폐쇄망 설치 파일 준비

GitHub 소스만으로는 인터넷 없는 PC에서 바로 실행할 수 없습니다. 인터넷 PC에서 패키지·모델·FFmpeg를 별도로 준비합니다. 인터넷 PC와 대상 PC의 Windows 아키텍처와 Python 버전은 같게 맞추며, 아래는 Windows x64 / Python 3.12 기준입니다.

## 1. 인터넷 PC에서 wheel 준비

깨끗하게 받은 저장소의 프로젝트 루트에서 실행합니다.

```powershell
py -3.12 -m venv .venv-download
.\.venv-download\Scripts\python.exe -m pip install --upgrade pip wheel
.\.venv-download\Scripts\python.exe -m pip download --only-binary=:all: -r .\requirements.txt -d .\wheelhouse
.\.venv-download\Scripts\python.exe -m pip download --only-binary=:all: pip setuptools wheel -d .\wheelhouse
```

wheel을 찾지 못하면 대상 Python/OS용 wheel 제공 여부를 확인합니다. 소스 압축파일만 받아도 오프라인 설치가 보장되는 것은 아닙니다. 화자 분리와 exe 빌드가 필요하면 각각 해당 문서의 wheel도 추가로 준비합니다.

## 2. 모델과 FFmpeg 준비

```powershell
.\.venv-download\Scripts\python.exe -m pip install huggingface_hub
.\.venv-download\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-small', local_dir='models/faster-whisper-small')"
```

모델 4종을 모두 받으려면 마지막 명령 대신 `.\.venv-download\Scripts\python.exe .\download_model.py`를 실행합니다. 대상 PC에서 선택할 모델을 반드시 준비하세요.

FFmpeg는 [FFMPEG_OFFLINE.md](FFMPEG_OFFLINE.md)에 따라 `tools/ffmpeg/bin/ffmpeg.exe`에 두고, 필요하면 Microsoft VC++ x64 런타임 설치 파일도 준비합니다. 화자 분리 모델은 [SPEAKER_DIARIZATION.md](SPEAKER_DIARIZATION.md)를 따릅니다.

사내 인증서 때문에 다운로드가 실패하면 관리자가 제공한 신뢰할 수 있는 인증서를 설정합니다. 인증서 검증을 끄지 않습니다.

```powershell
$env:SSL_CERT_FILE = 'C:\path\to\company-root-ca.pem'
$env:REQUESTS_CA_BUNDLE = 'C:\path\to\company-root-ca.pem'
```

## 3. 대상 PC로 옮길 파일

- 저장소의 소스·설정 예시·requirements·문서
- 준비한 `wheelhouse/`, `models/`, `tools/`
- 필요할 때 `wheelhouse-diarization/`과 VC++ 런타임 설치 파일

개인 `.venv`, `.git`, 녹음·출력 파일과 실제 `app_settings.json`은 반입 묶음에서 제외합니다. 사용 이력이 없는 깨끗한 소스 복사본에 자산을 추가하면 분류하기 쉽습니다. 이 반입 패키지는 GitHub 업로드용 소스 묶음과 용도가 다릅니다.

## 4. 폐쇄망 PC 설치 및 실행

복사한 프로젝트 루트에서 실행합니다. 이 단계에서는 pip 업그레이드도 로컬 wheel만 사용합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

[INSTALL.md](INSTALL.md)의 LLM 설정을 진행하고 실행합니다.

```powershell
.\.venv\Scripts\python.exe .\launcher.py
```

[http://127.0.0.1:5000](http://127.0.0.1:5000)에 접속합니다. 인터넷 없이 STT를 실행할 수 있어도 회의록 생성에는 설정한 LLM 서버에 대한 접속이 필요합니다.
