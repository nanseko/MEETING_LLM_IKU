# 다른 PC 설치 및 실행

아래 명령은 **Windows PowerShell에서 프로젝트 루트를 현재 폴더로 둔 상태**로 실행합니다. 프로젝트 루트는 `launcher.py`, `requirements.txt`, `source/`가 함께 있는 폴더입니다. 폴더 이름이나 사용자 계정 경로는 자유롭게 바꿀 수 있습니다.

## 1. 준비 사항

- Windows 10/11 x64와 Python 3.12 x64. 원본 환경은 Python 3.12.10입니다.
- 초기 설치에는 인터넷 연결이 필요합니다. 폐쇄망은 [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md)를 따릅니다.
- 음성 처리용 STT 모델, FFmpeg, 접속 가능한 LLM 서버가 필요합니다.
- CPU 실행이 기본입니다. 이 안내는 CUDA 설정을 요구하지 않습니다.

Python은 [Python 공식 Windows 다운로드](https://www.python.org/downloads/windows/)에서 설치하고 확인합니다.

```powershell
py -3.12 --version
py -3.12 -c "import struct; print(struct.calcsize('P') * 8)"
```

두 번째 출력은 `64`여야 합니다. `py`가 없으면 Python 3.12를 가리키는 `python`으로 바꿉니다.

## 2. 소스 준비와 Python 패키지 설치

GitHub에서 받은 ZIP을 풀거나 저장소를 clone한 뒤 그 폴더로 이동합니다. 이 안내에는 특정 PC의 절대 경로가 필요하지 않습니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

가상환경을 활성화하지 않고 Python 실행 파일을 직접 사용하므로 `Activate.ps1` 실행 정책을 변경할 필요가 없습니다. Python 패키지는 가상환경마다 새로 설치하며 다른 PC의 `.venv`를 복사하지 않습니다.

## 3. STT 모델 준비

첫 사용에는 기본 선택 모델인 **small 하나만** 준비해도 됩니다.

```powershell
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Systran/faster-whisper-small', local_dir='models/faster-whisper-small')"
```

`huggingface_hub`는 기본 패키지의 의존성으로 설치됩니다. 직접 import가 되지 않으면 같은 가상환경에 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install huggingface_hub
```

모델 4종을 모두 준비하려면 제공된 도우미를 사용합니다. 모든 모델을 다운로드하므로 시간과 디스크 공간이 더 필요합니다.

```powershell
.\.venv\Scripts\python.exe .\download_model.py
```

앱은 `models/faster-whisper-<선택한 모델>` 폴더를 직접 검사합니다. 필요한 파일은 `model.bin`, `config.json`, `tokenizer.json`, `vocabulary.*`입니다. Web UI는 모델이 없을 때 자동으로 내려받지 않습니다. 모델을 small만 받았다면 설정 화면에서도 small을 선택하세요. Web UI에서는 `WHISPER_MODEL` 환경변수만 바꾸어 모델 폴더 검사를 대신할 수 없습니다.

## 4. FFmpeg와 Windows 런타임

[FFmpeg 공식 다운로드 안내](https://ffmpeg.org/download.html)의 Windows 빌드 링크에서 실행 파일을 받아 다음 위치에 둡니다.

```text
tools/ffmpeg/bin/ffmpeg.exe
```

```powershell
.\tools\ffmpeg\bin\ffmpeg.exe -version
```

이미 PATH의 `ffmpeg -version`이 동작하면 추가 복사는 필요하지 않습니다. 다른 경로는 [FFMPEG_OFFLINE.md](FFMPEG_OFFLINE.md)를 참고하세요.

네이티브 DLL 관련 오류가 나면 [Microsoft 공식 Visual C++ Redistributable 안내](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)에서 x64 런타임을 설치합니다. 설치 후 앱을 다시 실행합니다.

## 5. LLM 연결 설정

배포본에는 실제 API URL, 모델명, 키가 없습니다. 다음 두 방법 중 하나로 설정합니다. 서버는 이 앱이 호출하는 OpenAI 호환 Chat Completions 형식과 연결되어야 합니다. URL에는 관리자가 제공한 API base URL을 입력하고 `/chat/completions` 전체 경로를 임의로 덧붙이지 않습니다.

### 방법 A: 앱의 설정 화면

```powershell
.\.venv\Scripts\python.exe .\launcher.py
```

[http://127.0.0.1:5000/settings](http://127.0.0.1:5000/settings)에서 `API URL`, `MODEL`, `API KEY`를 입력하고 저장합니다. `source/app_settings.json`은 앱이 자동으로 만듭니다. 외부 PC에서는 사내 서버에 접근하지 못할 수 있으므로 서버 접속 경로도 확인하세요.

### 방법 B: 설정 예시 복사

실제 설정 파일이 아직 없을 때만 아래 명령으로 예시를 복사합니다. 이미 설정한 경우에는 기존 파일을 편집하세요.

```powershell
Copy-Item .\source\app_settings.example.json .\source\app_settings.json
notepad .\source\app_settings.json
```

`api_url`, `api_model`, `api_key`의 빈 문자열을 실제 값으로 변경합니다. 예시의 `recording_dir` 값 `uploads`는 `source/`를 기준으로 해석되므로 PC마다 경로를 바꿀 필요가 없습니다. JSON은 UTF-8로 저장합니다.

환경변수로 설정할 수도 있습니다. 아래 값은 예시이므로 실제 서버 정보로 바꾸세요.

```powershell
$env:INTERNAL_LLM_URL = 'https://llm.example.com/v1'
$env:INTERNAL_LLM_MODEL = 'YOUR_MODEL_NAME'
$env:INTERNAL_LLM_API_KEY = 'YOUR_API_KEY'
.\.venv\Scripts\python.exe .\launcher.py
```

저장된 설정 파일의 값이 환경변수보다 우선합니다. `.env` 파일은 앱이 자동으로 읽지 않습니다. 새 PowerShell 창에서는 환경변수를 다시 설정해야 합니다. API 키가 든 실제 설정 파일은 `.gitignore`로 제외됩니다.

## 6. 실행과 확인

```powershell
.\.venv\Scripts\python.exe .\launcher.py
```

브라우저에서 [http://127.0.0.1:5000](http://127.0.0.1:5000)에 접속합니다. 다른 PowerShell 창에서 상태를 확인할 수 있습니다.

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

정상 응답은 `status: ok`입니다. 이 응답은 웹 서버 상태만 확인하며, 모델·FFmpeg·LLM 연결 성공을 보증하지 않습니다. 설정을 마친 뒤 짧은 음성 파일을 업로드하여 STT, LLM, DOCX 다운로드까지 실제로 확인하세요.

5000번 포트를 다른 프로그램이 사용하면 아래처럼 변경합니다.

```powershell
$env:FLASK_PORT = '5001'
.\.venv\Scripts\python.exe .\launcher.py
```

이때 접속 주소도 `http://127.0.0.1:5001`로 변경합니다. 선택형 화자 분리는 기본적으로 OFF이며 [SPEAKER_DIARIZATION.md](SPEAKER_DIARIZATION.md)에 따라 추가 설치합니다.
