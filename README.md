# HARU Mastering v3.6 FINAL REPORT SYNC

Windows 10/11용 오프라인 중심 배치 마스터링·자동 품질검사·자동수정 프로그램입니다.

## 사용자는 이것만 하면 됩니다

1. Suno Studio에서 WAV를 내보냅니다.
2. 15곡을 한 폴더에 모읍니다.
3. `RUN.bat` 실행 → 폴더 선택 → 장르 선택 → `품질+` → 시작.
4. 완료 후 `01_RELEASE_READY` 폴더의 WAV만 유튜브·음원유통에 사용합니다.

LUFS, LRA, dBTP, 위상, Tail, 코덱 피크와 sample 지연을 사용자가 직접 판단할 필요가 없습니다.

## v3.6 핵심 변경: 최종 WAV 보고서 동기화

v3.5까지는 코덱 안전을 위해 최종 WAV 전체 게인을 낮춘 곡에서 LUFS와 True Peak는 다시 측정했지만, 일부 Tail 수치가 코덱 감쇠 전 값으로 남을 수 있었습니다. 완료 안내문에도 과거 버전인 `v3.2`가 표시되는 경우가 있었습니다.

v3.6은 모든 후처리가 끝난 실제 배포용 WAV를 다시 읽어 다음 결과를 동기화합니다.

- HTML Quality Gate의 최종 LUFS·True Peak·Tail RMS·마지막 sample
- JSON Quality Gate의 `processed` 및 Tail 판정값
- CSV의 기존 Tail 열과 최종 Tail 전용 열
- `자동해결_결과.txt`의 실행 버전
- `STUDIO_문제곡_보완_프롬프트.txt`의 실행 버전

CSV에 다음 최종 확인 열이 추가됩니다.

- `tail_final_rms_dbfs`
- `tail_final_last_sample_dbfs`
- `tail_final_hard_cut`
- `tail_final_energetic_end`
- `tail_metrics_source=final_master_after_codec`

코덱 감쇠가 적용된 곡은 `tail_after_RMS`와 `tail_after_rms_dbfs`도 최종 WAV 값으로 갱신됩니다.

## 전체 자동 처리 구조

```text
원본 WAV
  ↓
채널·장르 프로필 마스터링
  ↓
복합 Quality Gate
  ├─ LUFS / 4x True Peak / clipping / DC
  ├─ full-band + 110 Hz 이하 stereo correlation
  ├─ 곡 전체 5구간 sample delay 진단
  ├─ duration loss
  ├─ LRA 감소 + 최종 LRA + Crest Factor 복합판정
  └─ 페이드 전 Tail 에너지 + 마지막 sample
  ↓
문제 자동수정
  ├─ 실제 다이내믹 위험 → Compressor 자동 완화, 최대 2회
  ├─ 그래도 위험 → EQ·Compressor 완전 우회 투명 마스터링
  ├─ 강한 끝신호 → 400→600→800→1200 ms 적응형 감쇠
  ├─ 작은 디지털 불연속 → 5~25 ms click-safe fade
  └─ 확정된 48 sample 이상 지연 → sample 자동정렬 후 재검사
  ↓
AAC 256 / MP3 320 round-trip 안전검사
  ├─ 코덱 피크 초과량 실측
  ├─ 필요한 감쇠량만 계산
  ├─ 최종 WAV에 투명 broadband gain 적용
  └─ 최대 3회 재검사, 총 감쇠 2 dB 제한
  ↓
최종 WAV 재분석 및 보고서 동기화
  ├─ LUFS / True Peak / Tail 재측정
  ├─ HTML / JSON / CSV 일치
  └─ 완료 안내문 v3.6 표기
  ↓
최종 분류
  ├─ 01_RELEASE_READY
  ├─ 02_NEEDS_REVIEW
  ├─ 03_REPORT
  └─ 04_CODEC_PREVIEW
```

## v3.5 Adaptive Tail Finish 유지

강한 신호로 끝나는 곡은 같은 원본 마스터 복사본을 기준으로 다음 후보를 순서대로 계산합니다.

```text
400 ms → 검사
600 ms → 검사
800 ms → 검사
1200 ms → 검사
```

- 안전 기준보다 0.5 dB 여유 있게 통과한 가장 짧은 페이드를 선택합니다.
- 후보를 연속으로 겹쳐 적용하지 않습니다.
- 선택된 페이드 한 번만 최종 WAV에 저장합니다.
- 1200 ms까지 적용해도 안전하지 않으면 억지로 RELEASE_READY에 넣지 않습니다.
- 지연 자동정렬이 발동한 곡도 정렬 후 적응형 Tail 검사를 다시 실행합니다.

## v3.4 Smart Delay Guard 유지

곡의 시작·중간·후반을 포함한 최대 5개 구간을 분석해 중앙값, 구간 일치도와 상관 신뢰도를 함께 봅니다.

```text
0~1 sample   : PASS
2~8 samples  : INFO, 배포 가능, 파일 이동 없음
9~47 samples : 경고 정보 기록, 배포 가능, 파일 이동 없음
48+ samples  : 여러 구간이 일치하고 신뢰도 0.70 이상일 때만 자동정렬
불일치 측정  : 억지로 이동하지 않고 보류
```

48 kHz에서 48 sample은 1 ms, 240 sample은 5 ms입니다. 자동정렬 전에는 마스터 복사본을 임시 백업하고, 재검사 결과가 개선되지 않으면 원상복구합니다.

## v3.3 코덱 자동감쇠 유지

AAC·MP3 피크가 높으면 실제 초과량을 계산해 최종 WAV를 필요한 만큼만 낮춥니다.

```text
필요 감쇠량 = 측정 코덱 피크 - (장르 ceiling - 추가 안전여유 0.10 dB)
```

EQ, Compressor, 편곡과 보컬 음색은 바꾸지 않습니다.

안전장치:

- 최대 자동감쇠 재검사 3회
- 한 번에 최대 1.50 dB
- 전체 최대 2.00 dB
- 매 감쇠 후 AAC·MP3를 다시 생성해 실제 True Peak 재측정
- 최종 WAV를 다시 분석해 HTML·JSON·CSV에 기록

## 복합 다이내믹 판정

LRA 감소량 하나만으로 정상곡을 탈락시키지 않습니다.

- 장르별 권장 LRA 감소량
- 최종 LRA 3.5 LU 이상 여부
- Crest Factor 손실 0.75 dB 이하 여부

최종 LRA가 충분하고 Crest Factor가 유지되거나 좋아졌다면 PASS입니다. 실제 다이내믹이 무너진 곡만 압축 완화와 투명 마스터링을 적용합니다.

## 기본 안전 원칙

- 원본 파일은 절대 덮어쓰지 않습니다.
- 기본 출력은 48 kHz / 24-bit WAV입니다.
- DeepFilterNet, noisereduce, Stem 분리는 정상곡에 자동 적용하지 않습니다.
- AI 복원은 실제 문제곡에만 선택적으로 사용합니다.
- 코덱 자동감쇠, sample 정렬과 Tail 수정은 최종 마스터 복사본에만 적용합니다.

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

## 설치·실행

```bat
INSTALL.bat
RUN.bat
```

기본 `RUN.bat`은 `Suno15_Mastering_v3_6.pyw`를 실행합니다.

## 자동 테스트

GitHub Actions / Windows / Python 3.12에서 다음을 자동 검사합니다.

- 전체 pytest
- 최종 WAV Tail RMS와 HTML·JSON 값 일치
- 코덱 감쇠 후 CSV Tail 값 재측정
- 완료 안내문 `v3.2~v3.5` → `v3.6` 자동교체
- 400 ms 실패 후 600 ms 통과 사례
- 가장 짧은 안전 페이드 선택
- 후보 페이드 비중첩·단일 저장
- -4 sample 측정값의 INFO·PASS 처리
- 5구간 240-sample 지연 확정 검출
- 실제 WAV sample 자동정렬과 길이 유지
- 코덱 초과량 자동감쇠
- RELEASE_READY / NEEDS_REVIEW 분리
- v2 / v3 / v3.2 / v3.3 / v3.4 / v3.5 / v3.6 runtime verification
- 모든 `.pyw` compile

## 저장소 운영

- `main`: 실제 음원 검증까지 끝난 안정 버전
- `upgrade/channel-aware-v2`: v3.6 개발·실파일 검증 브랜치
- Draft PR #2는 v3.6 실제 Suno WAV 검증 후에만 `main`에 병합합니다.
