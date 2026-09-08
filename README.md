# HARU Mastering v3.2 AUTO FINISH

Windows 10/11용 오프라인 중심 배치 마스터링·자동 품질검사·자동수정 프로그램입니다.

## 사용자는 이것만 하면 됩니다

1. Suno Studio에서 WAV를 내보냅니다.
2. 15곡을 한 폴더에 모읍니다.
3. `RUN.bat` 실행 → 폴더 선택 → 장르 선택 → `품질+` → 시작.
4. 완료 후 `01_RELEASE_READY` 폴더의 WAV만 유튜브/음원유통에 사용합니다.

LUFS, LRA, dBTP, 위상, Tail을 사용자가 직접 판단할 필요가 없습니다.

## v3.2 자동 처리 구조

```text
원본 WAV
  ↓
채널/장르 프로필 마스터링
  ↓
복합 Quality Gate
  ├─ LUFS / 4x True Peak / clipping / DC
  ├─ full-band + 110 Hz 이하 stereo correlation
  ├─ residual delay ±1 sample
  ├─ duration loss
  ├─ LRA 감소 + 최종 LRA + Crest Factor 복합판정
  └─ 페이드 전 Tail 에너지 + 마지막 sample
  ↓
문제 자동수정
  ├─ 실제 다이내믹 위험 → Compressor 자동 완화, 최대 2회
  ├─ 그래도 위험 → EQ/Compressor 완전 우회 투명 마스터링
  ├─ 큰 끝신호 → 약 400 ms 음악적 감쇠
  ├─ 작은 디지털 불연속 → 5~25 ms click-safe fade
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

## v3.2에서 달라진 다이내믹 판정

LRA 감소량 하나만으로 정상곡을 탈락시키지 않습니다.

다음 조건을 함께 봅니다.

- 장르별 권장 LRA 감소량
- 최종 LRA가 3.5 LU 이상인지
- Crest Factor 손실이 0.75 dB 이하인지

예를 들어 LRA가 권장량보다 더 줄었어도 최종 LRA가 충분하고 Crest Factor가 유지되거나 좋아졌다면 PASS로 처리합니다. 실제로 다이내믹이 무너진 곡만 압축 완화와 투명 마스터링을 적용합니다.

장르별 권장 LRA 감소량:

- OLD POP: 0.60 LU
- BALLAD: 0.80 LU
- JAZZ: 0.50 LU
- R&B: 0.90 LU
- SOUL: 0.80 LU
- CHANSON: 0.50 LU
- CHILI EN / JP: 0.80 LU
- SHOWA JP: 0.50 LU

## v3.2 Tail 자동처리

프로그램은 페이드를 적용하기 전에 마지막 100 ms의 에너지를 먼저 기록합니다.

- End RMS가 높은 곡: 약 400 ms의 긴 음악적 fade
- 조용하지만 마지막 sample이 남은 곡: 25 ms click-safe fade
- 거의 정상인데 마지막 sample만 남은 곡: 5 ms micro fade

따라서 마지막 sample을 0으로 만든 뒤 원래 큰 끝신호가 숨겨지는 문제를 방지합니다. 보고서에는 `tail_before_RMS`, `tail_fix_mode`, `tail_after_RMS`가 기록됩니다.

## 기본 안전 원칙

- 원본 파일은 절대 덮어쓰지 않습니다.
- 기본 출력은 48 kHz / 24-bit WAV입니다.
- 기존 5 ms / 240-sample limiter 지연은 latency compensation + 회귀 테스트로 방지합니다.
- DeepFilterNet, noisereduce, stem 분리는 정상곡에 자동 적용하지 않습니다.
- AI 복원은 실제 문제곡에만 선택적으로 사용합니다.
- 자동 해결 한도 초과 시 수동 EQ 안내 대신 원본 WAV 재수출 또는 해당 곡 재생성을 권장합니다.

## 결과 폴더

```text
MASTER_장르_AUTO_날짜시간
├─ 01_RELEASE_READY       ← 이것만 사용
├─ 02_NEEDS_REVIEW        ← 자동 해결 한도 초과, 배포하지 않음
├─ 03_REPORT
│  ├─ 초보자_최종판정.txt
│  ├─ 자동해결_결과.txt
│  ├─ mastering_report.csv
│  ├─ HARU_QUALITY_GATE.html
│  └─ HARU_QUALITY_GATE.json
└─ 04_CODEC_PREVIEW
```

## 설치 / 실행

기본 설치:

```bat
INSTALL.bat
```

기본 실행(v3.2):

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
- 안전한 LRA 변화와 실제 다이내믹 붕괴 구분
- 큰 끝신호의 400 ms 자동 감쇠
- 조용한 Hard Cut의 25 ms 자동 fade
- RELEASE_READY / NEEDS_REVIEW 분리
- v2 core / v3 feature / v3 runtime / v3.2 runtime verification
- v1 / v2 / v3 / v3.2 `.pyw` compile

## 저장소 운영

- `main`: 실제 음원 검증까지 끝난 안정 버전
- `upgrade/channel-aware-v2`: v3.2 개발/실파일 검증 브랜치
- Draft PR #2는 실제 Suno WAV 검증이 끝날 때까지 `main`에 병합하지 않습니다.
