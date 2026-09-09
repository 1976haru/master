# HARU Mastering v3.7.2 GUARANTEED CSV SYNC

Windows 10/11용 오프라인 중심 15곡 배치 마스터링·자동 품질검사·자동수정 프로그램입니다.

## 사용자는 이것만 하면 됩니다

1. Suno Studio에서 WAV를 내보냅니다.
2. 15곡을 한 폴더에 모읍니다.
3. `RUN.bat` 실행 → 폴더 선택 → 장르 선택 → `품질+` → 시작.
4. 완료 후 `01_RELEASE_READY` 폴더의 WAV만 유튜브·음원유통에 사용합니다.

## v3.7.2 핵심 변경: 최종 CSV 보증 동기화

v3.7.1 실음원 검증에서 코덱 전체감쇠 문제는 해결되어 08번·12번이 다시 약 -14 LUFS를 유지했지만, 결과 CSV에는 v3.7.1 전용 열이 생성되지 않는 경우가 있었습니다.

원인은 v3.6.1 부모 동기화 단계가 실제 실사용 경로에서는 확실히 실행되지만 `final_LRA`를 새 열로 만들지 않고 이미 존재할 때만 갱신하도록 되어 있었고, 이후 어댑터 후처리에 의존했기 때문입니다.

v3.7.2는 부모 v3.6.1 동기화 함수 자체를 v3.7.2 함수로 교체합니다. 따라서 상속·후처리 순서와 무관하게 다음 열을 반드시 생성합니다.

- `final_LRA`
- `final_lufs_delta_lu`
- `final_lufs_within_tolerance`
- `codec_strategy`
- `final_metrics_sync_version=v3.7.2`

최종 수치는 실제 MASTER WAV를 다시 분석해 기록하며, MASTER 파일이 이미 다음 폴더로 정리된 이후에도 찾습니다.

- 출력 폴더 루트
- `01_RELEASE_READY`
- `02_NEEDS_REVIEW`

CSV는 출력 폴더의 `mastering_report.csv`와 `03_REPORT/mastering_report.csv`를 동일하게 갱신합니다.

## v3.7.1 LUFS 보존 코덱 전략 유지

코덱 피크가 위험해도 최종 MASTER WAV 전체를 먼저 낮추지 않습니다.

```text
목표 LUFS로 마스터링
  ↓
AAC 256 / MP3 320 codec 검사
  ↓ unsafe
True Peak ceiling을 0.50 dB 낮춰 원본에서 재렌더
  ↓
LUFS / Dynamics / Tail / Delay 재검사
  ↓
codec 재검사
  ↓
최대 4회
```

코덱 안전과 목표 LUFS ±0.20 LU를 함께 만족하지 못하는 파일은 RELEASE_READY에 억지로 넣지 않습니다.

## v3.7 멀티장르 유지

기본 선택은 `OLD POP`입니다.

빠른 선택:

- OLD POP
- 日本シニア
- 쇼와 일본가요
- K-POP
- 동요·키즈팝
- 발라드

전체 23개 장르를 지원하며 일본 시니어, 엔카, 트로트, 일본어 발라드, 시티팝, 칠리랩, 팝, R&B, 소울, 재즈, 샹송, 어쿠스틱, 록, 로파이, 연주·뉴에이지, 기타·일반형 등을 선택할 수 있습니다.

각 장르는 이름뿐 아니라 목표 LUFS·True Peak·LRA·EQ·압축·Quality Gate 프로필에 연결됩니다.

## 기존 자동 품질 기능

- v3.6.1 최종 WAV/HTML/JSON/CSV 재측정
- v3.6 최종 Tail 동기화
- v3.5 Adaptive Tail 400→600→800→1200ms
- v3.4 Smart Delay Guard 및 확정 지연 자동정렬
- Dynamics Guard 및 투명 마스터링
- 저역 스테레오 상관 검사
- clipping / DC / duration / Tail / codec 검사
- `01_RELEASE_READY` / `02_NEEDS_REVIEW` 자동분리

## 결과 폴더

```text
MASTER_장르_AUTO_날짜시간
├─ 01_RELEASE_READY
├─ 02_NEEDS_REVIEW
├─ 03_REPORT
│  ├─ 초보자_최종판정.txt
│  ├─ 자동해결_결과.txt
│  ├─ mastering_report.csv
│  ├─ HARU_QUALITY_GATE.html
│  └─ HARU_QUALITY_GATE.json
└─ 04_CODEC_PREVIEW
```

## 설치·실행

```bat
INSTALL.bat
RUN.bat
```

기본 `RUN.bat`은 `Suno15_Mastering_v3_7_2.pyw`를 우선 실행합니다.

구형 `Suno15_Mastering.pyw`를 직접 실행하지 마세요.

## v3.7.2 자동 테스트

Windows / Python 3.12 CI에서 다음을 검사합니다.

- 전체 pytest
- v2~v3.7.1 기존 runtime 회귀검사
- v3.7.2 부모 CSV synchronizer patch 확인
- MASTER WAV가 `01_RELEASE_READY`에 있는 경우 최종 수치 동기화
- MASTER WAV가 `02_NEEDS_REVIEW`에 있는 경우 최종 수치 동기화
- `final_LRA` 신규 열 강제 생성
- `final_lufs_delta_lu` 및 허용오차 판정 생성
- `codec_strategy=ceiling_rerender_preserve_loudness`
- `final_metrics_sync_version=v3.7.2`
- root CSV와 `03_REPORT` CSV의 신규 열 일치
- 완료 안내문 v3.7.2 교체
- 모든 `.pyw` compile

## 저장소 운영

- `main`: 실제 음원 검증까지 끝난 안정 버전
- `upgrade/channel-aware-v2`: 개발·실파일 검증 브랜치
- Draft PR #2는 v3.7.2 실제 Suno WAV와 CSV 재검증 후에만 `main`에 병합합니다.
