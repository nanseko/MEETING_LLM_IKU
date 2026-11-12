# GitHub 저장소 관리

업로드 대상은 [nanseko/MEETING_LLM_IKU](https://github.com/nanseko/MEETING_LLM_IKU)입니다. 로컬 `upload_git` 폴더의 **내용물**이 저장소 루트에 대응합니다. 상위 개발 폴더나 `upload_git` 폴더 자체를 한 단계 더 감싸서 올리지 않습니다.

## 폴더 구조

- `docs/`: README, 설치·사용·오프라인·exe 안내와 실행용 STT 보정 규칙을 포함한 Markdown 문서
- `source/`: Python 소스, HTML·CSS·JavaScript와 비밀정보 없는 설정 예시
- 루트: 실행·모델 다운로드·빌드 도우미, requirements, `.gitignore`, `UPLOAD_MANIFEST.txt`

정확한 배포 파일 목록과 SHA-256은 [UPLOAD_MANIFEST.txt](../UPLOAD_MANIFEST.txt)를 참고합니다. 앱은 `docs/stt_correction_rules.md`를 실행 중 읽으므로 소스와 함께 유지해야 합니다.

## 제외 파일

`.gitignore`는 아래 로컬 자산과 개인 데이터를 제외합니다.

- `.venv*`, `__pycache__`, 테스트 캐시
- `models/`, `tools/`, `wheelhouse*/`와 모델·실행 바이너리
- `build/`, `dist/`, 압축 배포 결과
- 녹음 업로드, STT/회의록 출력, 변환 기록, 로그
- 실제 `app_settings.json`, `.env`와 인증 키 파일

실행 후 생성된 파일도 같은 기준으로 제외됩니다. 제외 파일을 강제로 추가하지 마세요. 새 PC 설치는 [INSTALL.md](INSTALL.md)를 따릅니다.

## 이후 업데이트

원격 저장소의 최신 브랜치와 파일을 확인한 뒤 변경사항을 반영합니다. 기존 이력을 강제로 덮어쓰지 않습니다. 소스나 문서를 변경하면 `UPLOAD_MANIFEST.txt`의 경로와 해시도 함께 갱신합니다. GitHub에 게시하는 `.md` 파일은 `docs/`에 둡니다.

원본 프로젝트에 LICENSE 파일이 없어 임의 라이선스를 추가하지 않았습니다. 다른 프로젝트의 LICENSE도 가져오지 않았습니다.
