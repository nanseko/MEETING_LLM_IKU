# 선택형 화자 분리

기본 실행에는 필요하지 않습니다. 사용하려면 같은 가상환경에 추가 패키지와 모델을 준비한 뒤 설정 화면의 Speaker-Diarization을 켭니다. 이 소스는 `pyannote.audio==3.3.0`과 로컬 `speaker-diarization-3.1` 구성을 사용합니다.

## 1. 패키지 설치

프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-diarization.txt
.\.venv\Scripts\python.exe -m pip check
```

requirements에는 pyannote 관련 버전, `torch==2.3.1`, `torchaudio==2.3.1`, `numpy<2`, `setuptools<81`이 지정되어 있습니다. 임의로 pyannote 4.x로 올리지 마세요. CPU용 PyTorch를 먼저 설치하려면 [PyTorch 공식 이전 버전 안내](https://pytorch.org/get-started/previous-versions/)의 2.3.1 항목을 참고합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r .\requirements-diarization.txt
```

## 2. 모델 다운로드

[speaker-diarization-3.1 모델 페이지](https://huggingface.co/pyannote/speaker-diarization-3.1)와 [segmentation-3.0 모델 페이지](https://huggingface.co/pyannote/segmentation-3.0)에서 Hugging Face 계정으로 이용 조건을 확인하고 필요한 접근 승인을 받습니다. 접근 권한이 있는 계정으로 로컬 로그인합니다. 토큰을 소스나 명령 기록에 직접 적지 않도록 대화형 로그인을 사용합니다.

```powershell
.\.venv\Scripts\python.exe -c "from huggingface_hub import login; login()"
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='pyannote/speaker-diarization-3.1', local_dir='models/pyannote-speaker-diarization-3.1')"
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='pyannote/segmentation-3.0', local_dir='models/pyannote-segmentation-3.0')"
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='pyannote/wespeaker-voxceleb-resnet34-LM', local_dir='models/wespeaker-voxceleb-resnet34-LM')"
```

필수 구조:

```text
models/
  pyannote-speaker-diarization-3.1/config.yaml
  pyannote-segmentation-3.0/config.yaml
  pyannote-segmentation-3.0/pytorch_model.bin
  wespeaker-voxceleb-resnet34-LM/config.yaml
  wespeaker-voxceleb-resnet34-LM/pytorch_model.bin
```

`voice-activity-detection` 모델을 별도로 준비할 필요는 없습니다. 앱은 로컬 pipeline config의 segmentation/embedding 참조를 로컬 체크포인트로 바꾸고, 화자 분리 실행 중 Hugging Face 오프라인 모드를 설정합니다.

## 3. 준비 상태 확인

```powershell
.\.venv\Scripts\python.exe -c "from source.diarization_service import diarization_status, validate_pyannote_runtime; validate_pyannote_runtime(); print(diarization_status())"
```

이 검사는 패키지 버전과 파일 존재 여부를 확인합니다. 실제 추론 확인은 앱에서 짧은 음성으로 수행합니다. 화자 라벨은 `Speaker 1`, `Speaker 2` 형태이며 STT 구간과 겹치는 시간으로 배정됩니다. 사람 이름을 자동으로 식별하는 기능은 아닙니다.

## 폐쇄망

같은 OS/Python의 인터넷 PC에서 wheel을 받습니다.

```powershell
.\.venv-download\Scripts\python.exe -m pip download --only-binary=:all: -r .\requirements-diarization.txt -d .\wheelhouse-diarization
```

기본 wheelhouse와 화자 분리 wheelhouse, 모델 3종을 대상 PC로 옮깁니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse --find-links .\wheelhouse-diarization -r .\requirements-diarization.txt
.\.venv\Scripts\python.exe -m pip check
```
