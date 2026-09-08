# HARU Mastering v3

Windows 10/11용 오프라인 중심 배치 마스터링·음원 진단·선택적 복원 프로그램입니다.

## 기본 원칙

- 원본 파일을 절대 덮어쓰지 않습니다.
- 정상곡은 불필요한 복원을 하지 않습니다.
- 먼저 분석하고, 문제가 있을 때만 최소한으로 처리합니다.
- 기본 마스터링은 AI 패키지가 없어도 동작합니다.
- 무거운 AI 복원 기능은 `INSTALL_AI_TOOLS.bat`로 별도 설치합니다.
- 기본 출력은 48 kHz / 24-bit WAV입니다.

## 채널 프로필

- `old_pop_lounge`: 따뜻하고 성숙하며 장시간 들어도 피곤하지 않은 사운드
- `old_pop_lounge_french_chanson`: 프랑스어 자음·모음과 대화형 보컬을 보존하는 샹송 프로필
- `chili_lab`: 가까운 보컬, 타이트한 저역, 도시적인 Chill Rap / Urban Soul
- `chili_lab_ja`: 일본어 모라 리듬과 발음 명료도를 보존하는 일본어 CHILI LAB
- `showa_seventies`: 1970년대 일본 New Music·포크·가요의 절제된 중저역과 부드러운 고역

## v3 처리 구조

```text
Input
  ↓
Channel Profile
  ↓
LUFS / True Peak / LRA / Spectrum / Stereo / DC 분석
  ↓
기본 Channel-Aware Mastering
  ↓
FFmpeg limiter latency compensation
  ↓
48 kHz / 24-bit WAV
  ↓
Quality Gate
  ├─ LUFS
  ├─ 4x True Peak
  ├─ clipping / DC
  ├─ full-band stereo correlation
  ├─ low-band(110 Hz 이하) stereo correlation
  ├─ residual delay samples
  ├─ duration loss
  └─ tail review
  ↓
PASS / WARN / FAIL
  ↓
HTML + JSON report
```

## 선택적 고급 기능

프로그램의 `⑤ 고급 복원 / 품질검사` 탭에서 사용할 수 있습니다.

### Noise Repair

`noisereduce` 기반 보수적 spectral-gate 처리를 사용합니다. 음악 전체에 강하게 적용하지 않고 실제 지속 노이즈가 있을 때만 사용합니다.

### DeepFilterNet

`Rikorose/DeepFilterNet`을 선택적 복원 엔진으로 연결합니다. MIT/Apache-2.0 계열이며, 보컬/음성성 노이즈 복원에 사용합니다. 실행 시 delay compensation을 켭니다.

### Vocal / Instrument Stem

`nomadkaraoke/python-audio-separator`를 선택적으로 연결합니다. MIT 라이선스 프로젝트이며 Vocal/Instrumental 등 stem 분리에 사용합니다. 모델은 첫 사용 때 다운로드될 수 있으며 캐시 후 로컬 실행이 가능합니다.

### Reference Assist

GPL 프로젝트 코드를 복사하지 않고 자체 bounded spectral matching을 구현했습니다. Reference와의 대역별 차이를 분석하되 채널 프로필의 `maxAutomaticEqDb` 이상으로 보정하지 않습니다. 전체 음량 차이는 EQ 보정에서 제거합니다.

### Codec Preview

완성 파일을 AAC 256 kbps / MP3 320 kbps로 인코딩한 뒤 다시 디코딩하여 LUFS와 True Peak를 측정합니다. 실제 플랫폼 압축 후 피크 변화를 미리 확인할 수 있습니다.

## 5 ms 지연 재발 방지

기존 프로그램에서 FFmpeg `alimiter`의 5 ms lookahead 때문에 48 kHz 기준 240 samples 지연이 발생했습니다.

v2/v3에서는 limiter에 latency compensation을 적용하고, Quality Gate와 자동 테스트에서 residual delay가 ±1 sample을 넘으면 FAIL 처리합니다. 240-sample 지연을 의도적으로 만든 회귀 테스트도 포함되어 있습니다.

## 설치

기본 설치:

```bat
INSTALL.bat
```

실행:

```bat
RUN.bat
```

선택적 AI 복원 도구 설치:

```bat
INSTALL_AI_TOOLS.bat
```

문제가 있을 때 v2 실행:

```bat
RUN_V2.bat
```

기존 v1.1 실행:

```bat
RUN_LEGACY.bat
```

## 자동 테스트

GitHub Actions에서 Windows + Python 3.12 환경으로 다음을 자동 검사합니다.

- 전체 pytest
- v2 core verification
- v3 feature verification
- v3 runtime import
- v1/v2/v3 `.pyw` compile

## 저장소 운영

- `main`: 검증된 안정 버전
- `upgrade/channel-aware-v2`: 현재 v3 개발/검증 브랜치
- 큰 변경은 Pull Request에서 테스트 후 병합
- 원본 음원, 출력 WAV, AI 모델, `.venv`, API 키는 Git에 저장하지 않음

## 현재 상태

v3 코드 통합은 완료 단계이며, Draft PR #2에서 실제 Suno WAV A/B 회귀 테스트와 GitHub Actions 검증 후 `main` 병합 여부를 결정합니다.
