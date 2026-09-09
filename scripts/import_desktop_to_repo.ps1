[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path $_ -PathType Container })]
    [string]$Source,

    [string]$Destination = "",

    [switch]$CommitAndPush
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git이 설치되어 있지 않거나 PATH에 없습니다. Git for Windows를 먼저 설치하세요."
}

if (-not (Get-Command robocopy -ErrorAction SilentlyContinue)) {
    throw "Windows robocopy를 찾을 수 없습니다."
}

if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$Source = (Resolve-Path $Source).Path
$Destination = (Resolve-Path $Destination).Path

if ($Source.TrimEnd('\') -eq $Destination.TrimEnd('\')) {
    throw "원본 폴더와 GitHub 저장소 폴더가 같습니다. 서로 다른 폴더를 지정하세요."
}

if (-not (Test-Path (Join-Path $Destination ".git") -PathType Container)) {
    throw "대상 폴더가 Git 저장소가 아닙니다: $Destination"
}

$excludeDirs = @(
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
    "input",
    "inputs",
    "output",
    "outputs",
    "exports",
    "logs",
    "cache",
    "temp",
    "tmp",
    "models"
)

$excludeFiles = @(
    "*.wav",
    "*.wave",
    "*.mp3",
    "*.flac",
    "*.aiff",
    "*.aif",
    "*.m4a",
    "*.ogg",
    "*.aac",
    "*.wma",
    "*.onnx",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.bin",
    "*.safetensors",
    ".env",
    ".env.*"
)

Write-Host "원본: $Source"
Write-Host "대상: $Destination"
Write-Host "소스코드를 복사하고 음원·모델·가상환경·출력물은 제외합니다."

$arguments = @(
    $Source,
    $Destination,
    "/E",
    "/COPY:DAT",
    "/DCOPY:DAT",
    "/R:1",
    "/W:1",
    "/XJ",
    "/NP",
    "/NFL",
    "/NDL",
    "/XD"
) + $excludeDirs + @("/XF") + $excludeFiles

& robocopy @arguments
$robocopyExitCode = $LASTEXITCODE

if ($robocopyExitCode -ge 8) {
    throw "robocopy 실패: 종료 코드 $robocopyExitCode"
}

Write-Host "`n복사 결과:"
& git -C $Destination status --short

if ($CommitAndPush) {
    & git -C $Destination add --all

    $changes = & git -C $Destination status --porcelain
    if ([string]::IsNullOrWhiteSpace(($changes -join "`n"))) {
        Write-Host "커밋할 변경 사항이 없습니다."
        exit 0
    }

    & git -C $Destination commit -m "feat: import existing desktop mastering application"
    & git -C $Destination push -u origin HEAD

    Write-Host "`nGitHub 업로드가 완료되었습니다."
} else {
    Write-Host "`n검토 후 다음 명령으로 업로드하세요:"
    Write-Host "git add --all"
    Write-Host "git commit -m 'feat: import existing desktop mastering application'"
    Write-Host "git push -u origin HEAD"
}
