# FFmpeg 준비

이 앱은 음성을 16 kHz mono WAV로 변환할 때 FFmpeg를 호출합니다. GitHub 소스 배포본에는 실행 파일이 포함되지 않습니다.

## Windows에서 준비

[FFmpeg 공식 다운로드 페이지](https://ffmpeg.org/download.html)의 Windows EXE 빌드 링크를 통해 내려받고, 압축 안의 `ffmpeg.exe`를 프로젝트의 다음 위치에 복사합니다.

```text
tools/ffmpeg/bin/ffmpeg.exe
```

`ffprobe.exe`, `ffplay.exe`는 현재 앱의 음성 변환에 필수는 아닙니다. 프로젝트 루트에서 확인합니다.

```powershell
.\tools\ffmpeg\bin\ffmpeg.exe -version
.\.venv\Scripts\python.exe -c "from source.audio_pipeline import find_ffmpeg_binary; print(find_ffmpeg_binary())"
```

## 자동 탐색 순서

1. `FFMPEG_BINARY` 환경변수에 지정한 파일
2. `tools/ffmpeg/bin/ffmpeg.exe`
3. `tools/ffmpeg/ffmpeg.exe`
4. `source/tools/ffmpeg/bin/ffmpeg.exe`
5. `source/ffmpeg/bin/ffmpeg.exe`
6. PATH의 `ffmpeg`

다른 폴더의 파일을 사용하려면 실행할 PowerShell 창에서 지정합니다.

```powershell
$env:FFMPEG_BINARY = 'C:\path\to\ffmpeg\bin\ffmpeg.exe'
& $env:FFMPEG_BINARY -version
.\.venv\Scripts\python.exe .\launcher.py
```

잘못된 `FFMPEG_BINARY` 값이 있으면 다른 경로로 자동 전환되지 않습니다. 필요 없으면 현재 세션에서 해제하세요.

```powershell
Remove-Item Env:FFMPEG_BINARY -ErrorAction SilentlyContinue
```

폐쇄망에서는 인터넷 PC에서 실행 파일을 받아 같은 상대 경로로 반입합니다. exe 배포 시에는 exe 옆 `tools/ffmpeg/bin/ffmpeg.exe`에 둡니다.
