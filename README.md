# HARU Mastering v3.7.1 — MULTI GENRE + LOUDNESS SAFE CODEC

Windows 10/11용 Suno 15곡 배치 마스터링·자동 품질검사·자동수정 프로그램입니다.

## 사용자는 이것만 하면 됩니다

1. Suno Studio에서 Full Song WAV를 내보냅니다.
2. 15곡을 한 폴더에 모읍니다.
3. `RUN.bat` 또는 `START_HERE.bat` 실행 → 폴더 → 장르 → `품질+` → 시작.
4. 완료 후 `01_RELEASE_READY`의 WAV만 유튜브·음원유통에 사용합니다.

`Suno15_Mastering.pyw`를 직접 열면 구형 FINAL v1.1 화면이 나오므로 직접 실행하지 않습니다.

## v3.7.1 핵심 변경

### 1. 코덱 안전과 목표 LUFS를 동시에 보호

v3.3 방식은 AAC/MP3 round-trip 피크가 높을 때 이미 만들어진 MASTER WAV 전체를 감쇠할 수 있었습니다. 코덱 피크는 안전해지지만 -14 LUFS 곡이 -15.5 LUFS 이하로 내려갈 수 있었습니다.

v3.7.1은 순서를 바꿉니다.

```text
마스터 생성 (-14 LUFS 목표)
  ↓
AAC 256 / MP3 320 codec 검사
  ↓ unsafe
True Peak ceiling -0.50 dB 낮춰 원본에서 다시 마스터링
  ↓
LUFS / Quality Gate 재검사
  ↓
codec 재검사
  ↓
최대 4회 반복
```

- 최종 WAV를 먼저 broadband 감쇠하지 않습니다.
- 매 재렌더는 같은 장르 목표 LUFS를 유지합니다.
- 최종 LUFS 허용오차는 ±0.20 LU입니다.
- 코덱 안전과 LUFS 기준을 동시에 만족하지 못하면 `02_NEEDS_REVIEW`로 남깁니다.
- 너무 조용한 파일을 PASS로 `01_RELEASE_READY`에 넣지 않습니다.

### 2. 최종 CSV 완전 동기화

실제 최종 MASTER WAV를 다시 분석해 다음 값을 CSV에 기록합니다.

- `final_LUFS`
- `final_dBTP`
- `final_LRA`
- `final_sample_peak_dbfs`
- `final_rms_dbfs`
- `final_crest_factor_db`
- `final_metrics_source=final_master_after_all_postprocessing`
- `final_lufs_delta_lu`
- `final_lufs_within_tolerance`
- `codec_strategy=ceiling_rerender_preserve_loudness`

### 3. 보고서·완료문구 버전 통일

- HTML: `HARU Mastering Quality Gate v3.7.1`
- 완료 TXT: `모든 곡이 v3.7.1 자동검사와 자동수정을 통과했습니다.`

## v3.7 멀티 장르 23개 유지

빠른 선택:

- OLD POP
- 日本シニア
- 昭和セブンティーズ
- K-POP
- 동요·키즈팝
- 발라드

전체 장르:

`OLD POP`, `한국 시니어 감성`, `日本シニア`, `쇼와 일본가요`, `엔카·歌謡曲`, `트로트`, `발라드`, `일본어 발라드`, `팝`, `K-POP`, `일본 시티팝`, `칠리랩 일본어`, `칠리랩 영어`, `R&B`, `소울`, `재즈`, `샹송`, `어쿠스틱·포크`, `록·밴드`, `동요·키즈팝`, `로파이·카페`, `연주·뉴에이지`, `기타·일반형`.

각 장르는 실제 target LUFS, True Peak, LRA, EQ, Compressor, Quality Gate 프로필에 연결됩니다.

## 전체 자동 처리 구조

```text
원본 WAV
  ↓
장르별 마스터링
  ↓
Quality Gate
  ├─ LUFS / 4x True Peak / clipping / DC
  ├─ full-band + 110 Hz 이하 stereo correlation
  ├─ 5구간 Smart Delay Guard
  ├─ LRA 감소 + 최종 LRA + Crest Factor
  └─ Tail / Hard Cut / Energetic End
  ↓
자동수정
  ├─ Compressor 완화
  ├─ 필요 시 투명 마스터링
  ├─ Adaptive Tail 400→600→800→1200 ms
  └─ 확정된 큰 지연만 sample 자동정렬
  ↓
Codec Safety
  ├─ AAC 256 / MP3 320 실측
  ├─ 0.50 dB 단위 lower-ceiling 재렌더
  ├─ 매번 LUFS + Quality Gate 재검사
  └─ 최대 4회
  ↓
최종 WAV 재분석
  ├─ LUFS / dBTP / LRA / Tail
  └─ HTML / JSON / CSV 동기화
  ↓
01_RELEASE_READY / 02_NEEDS_REVIEW / 03_REPORT
```

## 기존 안전 기능 유지

- v3.6.1: 최종 WAV 수치 동기화, Tail INFO guard
- v3.6: 최종 Tail 동기화
- v3.5: 적응형 Tail
- v3.4: 5구간 Smart Delay Guard
- v3.3: codec round-trip 검사 기반 기능
- v3.2: 자동완성·투명 마스터링·Dynamics Gate

기본 출력은 48 kHz / 24-bit WAV이며 원본 파일은 덮어쓰지 않습니다.

## 설치·실행

```bat
INSTALL.bat
RUN.bat
```

기본 `RUN.bat`은 `Suno15_Mastering_v3_7_1.pyw`를 우선 실행합니다.

창 제목:

```text
HARU / SUNO 15-SET MASTERING v3.7.1 - LOUDNESS SAFE CODEC
```

## 자동 테스트

GitHub Actions / Windows / Python 3.12에서 다음을 자동 검사합니다.

- 전체 pytest
- v2~v3.7 기존 runtime 호환성
- v3.7.1 codec checker가 MASTER WAV를 선감쇠하지 않는지 확인
- lower-ceiling 0.50 dB / 최대 4회 설정 확인
- `final_LRA` 실제 WAV 동기화
- 최종 LUFS 허용오차 열 생성
- 완료문구·HTML 버전 v3.7.1
- 23개 장르 프로필
- 모든 `.pyw` compile

## 저장소 운영

- `main`: 실제 음원 검증까지 끝난 안정 버전
- `upgrade/channel-aware-v2`: 현재 개발·실파일 검증 브랜치
- Draft PR #2는 실제 15곡 재검증 후에만 `main`에 병합합니다.
