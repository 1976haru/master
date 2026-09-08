# HARU Mastering v3.1 AUTO FINISH

Windows 10/11용 오프라인 중심 배치 마스터링·자동 품질검사·자동수정 프로그램입니다.

## 사용자는 이것만 하면 됩니다

1. Suno Studio에서 WAV를 내보냅니다.
2. 15곡을 한 폴더에 모읍니다.
3. `RUN.bat` 실행 → 폴더 선택 → 장르 선택 → `품질+` → 시작.
4. 완료 후 `01_RELEASE_READY` 폴더의 WAV만 유튜브/음원유통에 사용합니다.

LUFS, LRA, dBTP, 위상, Tail을 사용자가 직접 판단할 필요가 없습니다.

## v3.1 자동 처리 구조

```text
원본 WAV
  ↓
채널/장르 프로필 마스터링
  ↓
Quality Gate
  ├─ LUFS / 4x True Peak / clipping / DC
  ├─ full-band + 110 Hz 이하 stereo correlation
  ├─ residual delay ±1 sample
  ├─ duration loss
  ├─ 장르별 LRA 감소 한도
  └─ Tail Hard Cut
  ↓
문제 자동수정 (최대 2회)
  ├─ LRA 과도 감소 → Compressor 자동 완화 후 재마스터
  ├─ Tail Hard Cut → 25 ms click-safe fade + 마지막 sample 0
  └─ AAC/MP3 피크 초과 → ceiling 0.20 dB씩 낮춰 재마스터
  ↓
AAC 256 / MP3 320 round-trip 안전검사
  ↓
최종 분류
  ├─ 01_RELEASE_READY
  ├─ 02_NEEDS_REVIEW
  ├─ 03_REPORT
  └─ 04_CODEC_PREVIEW
```

## 장르별 다이내믹 보호

자동 재마스터링 기준은 모든 장르에 똑같이 적용하지 않습니다.

- OLD POP: LRA 감소 최대 0.60 LU
- BALLAD: 0.80 LU
- JAZZ: 0.50 LU
- R&B: 0.90 LU
- SOUL: 0.80 LU
- CHANSON: 0.50 LU
- CHILI EN / JP: 0.80 LU
- SHOWA JP: 0.50 LU

OLD POP/SHOWA/Chanson은 여백을 더 강하게 보존하고 R&B/CHILI는 장르 특성상 조금 더 넓게 허용합니다.

## 기본 안전 원칙

- 원본 파일은 절대 덮어쓰지 않습니다.
- 기본 출력은 48 kHz / 24-bit WAV입니다.
- 기존 5 ms / 240-sample limiter 지연은 latency compensation + 회귀 테스트로 방지합니다.
- DeepFilterNet, noisereduce, stem 분리는 정상곡에 자동 적용하지 않습니다.
- AI 복원은 실제 문제곡에만 선택적으로 사용합니다.

## 결과 폴더

```text
MASTER_장르_AUTO_날짜시간
├─ 01_RELEASE_READY       ← 이것만 사용
├─ 02_NEEDS_REVIEW        ← 자동 해결 한도 초과, 배포하지 않음
├─ 03_REPORT
│  ├─ 초보자_최종판정.txt
│  ├─ mastering_report.csv
│  ├─ HARU_QUALITY_GATE.html
│  └─ HARU_QUALITY_GATE.json
└─ 04_CODEC_PREVIEW
```

`초보자_최종판정.txt`에는 `배포 가능` 또는 `배포 보류 곡 있음`이 큰 글자 대신 단순 문장으로 기록됩니다.

## 설치 / 실행

기본 설치:

```bat
INSTALL.bat
```

기본 실행(v3.1):

```bat
RUN.bat
```

선택적 AI 도구 설치:

```bat
INSTALL_AI_TOOLS.bat
```

문제가 있을 때 이전 버전으로 즉시 복귀:

```bat
RUN_V3.bat
RUN_V2.bat
RUN_LEGACY.bat
```

## 선택적 고급 기능

`⑤ 고급 복원 / 품질검사` 탭에는 다음 기능이 유지됩니다.

- noisereduce Noise Repair
- DeepFilterNet
- python-audio-separator Vocal / Instrument Stem
- 자체 bounded Reference Assist
- 수동 AAC/MP3 Codec Preview
- 수동 원본 ↔ 마스터 Quality Gate

이 기능들은 정상곡에 무조건 적용하지 않습니다.

## 자동 테스트

GitHub Actions / Windows / Python 3.12에서 다음을 자동 검사합니다.

- 전체 pytest
- 240-sample 지연 검출 회귀 테스트
- Tail Hard Cut 검출 및 자동 fade 테스트
- RELEASE_READY / NEEDS_REVIEW 분리 테스트
- v2 core / v3 feature / v3 runtime / v3.1 runtime verification
- v1 / v2 / v3 / v3.1 `.pyw` compile

## 저장소 운영

- `main`: 실제 음원 검증까지 끝난 안정 버전
- `upgrade/channel-aware-v2`: v3.1 개발/실파일 검증 브랜치
- Draft PR #2는 실제 Suno WAV 검증이 끝날 때까지 `main`에 병합하지 않습니다.
