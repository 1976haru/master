# 데스크톱 프로그램을 GitHub로 옮기는 방법

저장소: `1976haru/master`

## 1. GitHub 저장소 복제

PowerShell을 열고 아래 명령을 실행합니다.

```powershell
cd "$env:USERPROFILE\Desktop"
git clone -b upgrade/channel-aware-v2 https://github.com/1976haru/master.git master-github
cd .\master-github
```

## 2. 기존 프로그램 폴더 복사와 업로드

아래 명령에서 `마스터링프로그램` 부분만 실제 데스크톱 폴더명으로 바꿉니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\import_desktop_to_repo.ps1 `
  -Source "$env:USERPROFILE\Desktop\마스터링프로그램" `
  -CommitAndPush
```

스크립트가 자동으로 제외하는 항목:

- `.venv`, `venv`, `__pycache__`
- WAV, MP3, FLAC 등 음원 파일
- ONNX, PT, PTH 등 대형 모델 파일
- `input`, `output`, `logs`, `cache`, `build`, `dist`
- `.env` 및 로컬 비밀설정

## 3. 업로드 확인

```powershell
git status
git log -3 --oneline
git remote -v
```

정상이면 현재 브랜치가 `upgrade/channel-aware-v2`이고, GitHub에 데스크톱 프로그램 소스가 표시됩니다.

## 주의

- 원본 음원과 마스터 결과물은 GitHub에 올리지 않습니다.
- 저장소는 현재 공개 상태이므로 API 키, 개인 경로, 계정정보, 유료 플러그인 파일을 커밋하지 않습니다.
- 기존 프로그램 폴더는 삭제하지 않습니다. `master-github`는 GitHub 작업용 복사본으로 유지합니다.
