# GitHub 소스 배포본 정리 내역

## 포함 범위

UsingLLM 회의록 생성기의 실행 소스, UI 자산, 실행용 STT 규칙, 의존성 목록, 모델 다운로드 도우미와 선택형 exe 빌드 구성을 선별했습니다. Markdown 파일 10개는 README와 STT 규칙을 포함하여 모두 `docs/`에 모았습니다. 소스와 설정 예시는 `source/`, 실행·빌드 도우미와 requirements는 루트에 둡니다.

총 30개 배포 파일의 경로와 SHA-256은 [UPLOAD_MANIFEST.txt](../UPLOAD_MANIFEST.txt)에 기록합니다. 실제 설정 대신 `source/app_settings.example.json`을 포함했습니다.

## 원본과의 차이

- 상위 원본 프로젝트의 실행 소스·문서·설정·녹음은 수정하지 않았습니다.
- 배포용 `source/app.py`와 `source/meeting_minutes_service.py`의 API URL·모델명·키 기본값 6개를 비웠습니다. 사용자가 설정 화면이나 환경변수로 입력합니다.
- `docs/stt_correction_rules.md`를 소스 실행과 exe 실행에서 모두 읽도록 배포용 `source/app.py`의 탐색 경로를 추가했습니다. 이전 위치를 읽는 방식도 유지합니다.
- `MeetingMinutesApp.spec`은 규칙 파일을 `docs/`에서 가져와 번들 내부 `docs/`에 포함합니다. `build_exe.ps1`도 문서 폴더 전체를 배포 폴더로 복사하도록 맞췄습니다.
- 공개 배포용 STT 규칙은 특정 조직·제품·산업의 고유 용어 목록을 제거하고 일반 회의의 문맥·용어·수치 보정 규칙으로 작성했습니다. UI의 특정 회사명과 회사 표시도 일반 명칭으로 바꿨습니다.
- 그 밖의 실행 로직과 기본 requirements는 유지합니다. 문서는 개인 PC 경로를 제거하고 다른 PC의 설치·설정 절차에 맞게 정리했습니다.
- `.gitignore`는 모델·바이너리·실제 설정·실행 데이터를 제외합니다. requirements는 직접 의존성의 버전을 지정하지만 전이 의존성 전체를 고정한 lockfile은 아닙니다.

## 제외 범위

모델 가중치, FFmpeg/VC++ 설치 파일, wheel 묶음, 가상환경, 캐시, 빌드 결과, 녹음, STT·회의록 결과, 작업 로그, 실제 설정과 기록 JSON은 배포하지 않습니다. 별도 준비 절차는 [INSTALL.md](INSTALL.md)와 [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md)에 있습니다.

## 검증 범위 (2026-11-12)

- Markdown 파일이 모두 `docs/`에 있고 문서 상대 링크와 파일 목록·해시가 유효한지 검사합니다.
- 소스 실행, exe 옆 외부 `docs/`, exe 번들 내부 `docs/`의 세 배치에서 STT 규칙 탐색을 검사합니다.
- Python/spec·JavaScript·PowerShell 문법과 문서의 PowerShell 예시를 검사합니다.
- 현재 PC의 Python 3.12.10과 기존 설치 패키지로 Flask 화면·정적 파일·health·설정 저장을 확인하고, 가상 데이터로 DOCX 생성과 재열기를 검사합니다. 외부 서버 연결은 차단합니다.
- 원본 파일 해시 유지와 Git 제외 규칙도 확인합니다.
- 공개 배포 파일에 기존 회사명·제품명·특정 산업 용어와 실제 API 기본값이 남아 있지 않은지 검사합니다.
- 실제 음성 STT, 화자 분리 추론, LLM API 호출, 다른 PC에 대한 신규 설치, exe 빌드는 수행하지 않았습니다.
