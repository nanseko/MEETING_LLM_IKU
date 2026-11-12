$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Test-PythonModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModuleName
    )

    .\.venv\Scripts\python.exe -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

$DistRoot = Join-Path $ProjectRoot "dist"
$BuildRoot = Join-Path $ProjectRoot "build"

if (Test-Path $DistRoot) {
    Get-ChildItem $DistRoot -Recurse -Force | ForEach-Object { $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly) }
    Remove-Item $DistRoot -Recurse -Force
}

if (Test-Path $BuildRoot) {
    Get-ChildItem $BuildRoot -Recurse -Force | ForEach-Object { $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly) }
    Remove-Item $BuildRoot -Recurse -Force
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip

if (Test-Path ".\wheelhouse") {
    .\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements.txt
    if (-not (Test-PythonModule "PyInstaller")) {
        .\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse pyinstaller
    }
} else {
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if (-not (Test-PythonModule "PyInstaller")) {
        .\.venv\Scripts\python.exe -m pip install pyinstaller
    }
}

if (Test-Path ".\requirements-diarization.txt") {
    if (Test-Path ".\wheelhouse-diarization") {
        .\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse-diarization -r requirements-diarization.txt
    } elseif (Test-Path ".\wheelhouse") {
        .\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements-diarization.txt
    } else {
        .\.venv\Scripts\python.exe -m pip install -r requirements-diarization.txt
    }
}

.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\MeetingMinutesApp.spec

$DistDir = ".\dist\MeetingMinutesApp"

if (Test-Path ".\models") {
    New-Item -ItemType Directory -Path (Join-Path $DistDir "models") -Force | Out-Null
    robocopy ".\models" (Join-Path $DistDir "models") /E /XD ".git" /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -le 7) {
        $global:LASTEXITCODE = 0
    } else {
        throw "robocopy failed while copying models."
    }
}

if (Test-Path ".\tools") {
    New-Item -ItemType Directory -Path (Join-Path $DistDir "tools") -Force | Out-Null
    robocopy ".\tools" (Join-Path $DistDir "tools") /E /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -le 7) {
        $global:LASTEXITCODE = 0
    } else {
        throw "robocopy failed while copying tools."
    }
}

$DocsPath = Join-Path $ProjectRoot "docs"
if (Test-Path -LiteralPath $DocsPath) {
    Copy-Item -LiteralPath $DocsPath -Destination $DistDir -Recurse -Force
}

Write-Host ""
Write-Host "Build complete:"
Write-Host "$ProjectRoot\dist\MeetingMinutesApp\MeetingMinutesApp.exe"
Write-Host ""
Write-Host "Run:"
Write-Host ".\dist\MeetingMinutesApp\MeetingMinutesApp.exe"
