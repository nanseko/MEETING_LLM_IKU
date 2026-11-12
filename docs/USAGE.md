# 사용 방법

## 기본 순서

1. 프로젝트 루트에서 `.\.venv\Scripts\python.exe .\launcher.py`를 실행합니다.
2. 브라우저로 [http://127.0.0.1:5000](http://127.0.0.1:5000)에 접속합니다.
3. 설정 화면에서 API URL·모델·키를 저장하고, 실제로 다운로드한 STT 모델을 선택합니다.
4. 홈에서 회의명, 언어(한국어/영어), 인원수와 참석자 정보를 입력합니다.
5. 녹음 파일을 선택하거나 브라우저 녹음을 시작합니다. 마이크 권한 요청을 허용합니다.
6. 변환을 실행하고 진행 상태에서 WAV 변환 → STT → LLM → DOCX 단계를 확인합니다.
7. 완료 후 DOCX를 다운로드하고 회의 내용과 대조하여 검토합니다.

지원 확장자는 `.mp3`, `.m4a`, `.wav`, `.aac`, `.flac`, `.ogg`, `.mp4`, `.webm`입니다. 브라우저 녹음은 localhost/127.0.0.1에서 사용하고, 마이크 권한이 거부되면 브라우저의 사이트 권한에서 변경합니다.

## 모델과 화자 분리

tiny/base/small/medium 중 선택할 수 있지만 해당 모델 폴더가 먼저 준비되어 있어야 합니다. CPU에서는 모델 크기와 음성 길이에 따라 처리 시간이 늘어날 수 있습니다. 기본값은 small입니다.

Speaker-Diarization을 켜려면 별도 패키지와 모델 3종이 필요합니다. 설정 화면의 준비 상태와 [SPEAKER_DIARIZATION.md](SPEAKER_DIARIZATION.md)를 확인하세요. 회의 인원수를 입력하면 화자 분리 시 화자 수 제약으로도 사용됩니다.

## 저장 위치와 보안 사업 옵션

소스 실행 시 녹음은 기본적으로 `source/uploads/`, 처리 결과와 작업 로그는 `source/outputs/`에 생성됩니다. 설정은 `source/app_settings.json`, 기록은 `source/conversion_history.json`에 저장됩니다. exe 실행 시에는 exe 옆에 생성됩니다.

보안 사업 옵션은 생성 완료 후 임시 업로드 파일을 삭제하고, 다운로드 후 브라우저의 정리 요청으로 해당 작업의 출력 폴더를 삭제합니다. 현재 코드는 출력 루트에 STT 디버그 사본도 만들기 때문에 이 옵션만으로 모든 생성 데이터가 삭제되지는 않습니다. 민감한 회의가 끝난 뒤 저장 폴더를 확인하세요. 변환 기록 삭제는 기록 항목을 지우는 동작이며 결과 파일 전체 삭제와는 다릅니다.

STT 후처리 규칙은 `docs/stt_correction_rules.md`에서 편집합니다. 이 파일은 실행에 사용되므로 삭제하지 마세요.

## 문제 해결

| 증상 | 확인할 항목 |
| --- | --- |
| `ModuleNotFoundError` | `.venv`의 Python으로 실행했는지 확인하고 `requirements.txt` 설치 |
| 선택 모델이 없거나 불완전하다는 오류 | `models/faster-whisper-<모델>` 아래에 실제 모델 파일이 있는지 확인 |
| FFmpeg를 찾을 수 없음 | `tools/ffmpeg/bin/ffmpeg.exe`, PATH 또는 `FFMPEG_BINARY` 확인 |
| LLM 호출 실패 | 설정 URL·모델명·키, 서버 접근 권한, 사내망/VPN과 서버 상태 확인 |
| 화자 분리 오류 | OFF로 기본 실행을 확인한 뒤 선택 패키지와 모델 준비 |
| DLL 오류 | Python x64와 Microsoft VC++ x64 런타임 확인 |
| 포트 사용 중 | `FLASK_PORT`를 다른 번호로 지정 |
| DOCX 다운로드 실패 | 같은 서버 실행 중 완료 직후 다운로드하고 서버가 재시작되지 않았는지 확인 |

현재 버전의 다운로드 라우트는 메모리에 있는 작업 상태를 사용합니다. 서버 재시작 후 이전 결과 다운로드가 실패하면 `source/outputs/<작업ID>/`의 실제 DOCX를 확인하세요.

추가 진단 자료는 `source/outputs/<작업ID>/job_process.log`, `progress.json`, `result.json`에 남습니다. 실제 회의 내용이나 키가 포함될 수 있으므로 GitHub에 업로드하지 않습니다.
