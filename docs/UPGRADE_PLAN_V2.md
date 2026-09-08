# HARU Mastering v2 업그레이드 계획

## 목표

현재의 고정 체인을 `분석 → 필요한 처리만 적용 → 자동 검증` 구조로 바꾼다. 마스터링뿐 아니라 입력 음원의 문제를 진단하고, 안전한 범위 안에서 복원·개선하는 기능을 단계적으로 추가한다.

## 1. 즉시 수정할 결함

### 1.1 처리 지연 보상

- 룩어헤드 리미터, STFT, 리샘플러가 만든 지연을 샘플 단위로 측정한다.
- 출력 앞부분의 지연을 제거하기 전에 입력 뒤에 충분한 패딩을 추가한다.
- 처리 후 원본과 상호상관으로 정렬을 다시 확인한다.
- 허용 잔여 지연: 최대 1 sample.

### 1.2 마지막 잔향 보존

- 처리 전 500 ms 무음 패딩을 추가한다.
- 렌더 후 -75 dBFS 이하가 안정적으로 유지되는 지점을 찾는다.
- 최소 100 ms 안전 꼬리를 남긴 뒤 자른다.
- 신호가 남아 있는 곡은 자동으로 출력 길이를 늘린다.

### 1.3 중고역 과상승 방지

- 2~5 kHz, 5~10 kHz를 별도로 측정한다.
- 자동 EQ는 채널 프로필의 상한을 넘지 못하게 한다.
- 치찰음이 감지되면 고역 부스트 대신 다이내믹 감쇄를 우선한다.

## 2. Channel Profile Engine

`config/channel_profiles.v2.json`을 읽어 채널별 기본 목표와 처리 상한을 적용한다.

- OLD POP LOUNGE: 장시간 청취 피로 억제, 따뜻한 성숙 보컬, 절제된 고역
- French Chanson: 프랑스어 발음, rubato, 대화형 보컬과 어쿠스틱 악기 보존
- CHILI LAB: 가까운 보컬, 타이트한 저역, 도시적인 공간, 훅 명료도
- 日本語 CHILI LAB: 일본어 모라 리듬과 자음 명료도 보존, 아이돌식 광택 금지
- 昭和セブンティーズ: 1970s New Music·포크의 중저역, 좁거나 자연스러운 스테레오, 부드러운 고역

프로필 값은 무조건 적용하는 EQ 값이 아니라 자동 처리의 최대 허용 변화량이다.

## 3. 분석 모듈

입력과 출력에 같은 분석기를 적용한다.

- Integrated / Short-term LUFS
- LRA
- Sample Peak / True Peak
- Crest Factor
- DC Offset
- Clipped Sample Count
- 대역별 에너지와 spectral tilt
- Stereo Correlation과 Side/Mid 비율
- 저역 모노 호환성
- 시작 무음, 마지막 신호, 처리 지연
- 음원 길이와 샘플레이트·비트 깊이

모든 결과는 곡별 JSON과 사람이 읽는 HTML 보고서로 저장한다.

## 4. 안전한 마스터링 체인

1. 입력 검사와 복사본 생성
2. DC 제거와 필요할 때만 초저역 HPF
3. 분석 기반 broad EQ / dynamic EQ
4. 매우 약한 압축 또는 병렬 압축
5. 프로필별 미세 saturation
6. M/S 저역 보호와 제한된 스테레오 조정
7. 2-pass LUFS 보정
8. 4x 이상 True Peak 검사와 리미팅
9. 지연·꼬리 보상
10. Quality Gate 통과 여부 판정

Quality Gate를 통과하지 못하면 원본을 보존하고 `WARN` 또는 `FAIL` 결과를 남긴다.

## 5. 마스터링을 넘어선 음원 향상

### 5.1 노이즈·험·클릭 진단

- 무음 또는 저레벨 구간에서 noise floor를 추정한다.
- 50/60 Hz hum과 배음을 감지한다.
- 클릭·팝·DC jump를 탐지한다.
- 문제가 확인된 경우에만 repair 모드를 제안한다.

### 5.2 보컬 중심 복원 — 선택 기능

DeepFilterNet 같은 음성 향상 모델은 전체 음악 믹스에 항상 적용하지 않는다. 보컬 stem이 분리됐고 실제 잡음이 확인된 경우에만 낮은 강도로 사용한다. 처리 전후 스펙트럼 손실과 금속성 artifact를 자동 비교한다.

### 5.3 Spectral Gate Repair — 선택 기능

- 일정한 히스·룸노이즈가 실제로 검출된 경우에만 spectral gate를 사용한다.
- 감소량을 낮게 제한하고 transient와 high-frequency decay 손실을 비교한다.
- 전체 음악에 기본 적용하지 않는다.
- 무음 구간이 없거나 noise profile 신뢰도가 낮으면 자동으로 건너뛴다.

### 5.4 Stem-aware Rescue — 실험 기능

- `python-audio-separator` 같은 통합 도구를 통해 보컬 / 드럼 / 베이스 / 기타 stem을 임시 분리한다.
- 보컬 치찰음, 베이스 공진, 드럼 피크를 stem별로 아주 약하게 제어한다.
- 원본과 재합성 결과의 null difference와 artifact score를 검사한다.
- 분리 artifact가 기준을 넘으면 전체 믹스 처리로 자동 복귀한다.
- 모델 파일은 Git에 넣지 않고 사용자의 로컬 캐시에 별도 저장한다.

### 5.5 Reference Assist — 선택 기능

참조곡과 음색·스테레오·다이내믹을 비교하되 그대로 복제하지 않는다. 차이를 보고서로 보여주고, 자동 EQ 변화량은 프로필 상한 안에서만 허용한다.

### 5.6 Codec Preview

- WAV 결과를 임시 AAC/MP3로 인코딩한다.
- 인코딩 후 True Peak와 고역 artifact를 다시 측정한다.
- 스트리밍 인코딩에서 피크가 넘는 결과를 사전에 차단한다.

## 6. 공개 프로젝트 활용 원칙

### 우선 채택 후보

- `pyloudnorm`: BS.1770 기반 LUFS 측정. MIT 라이선스.
- `libebur128` 또는 FFmpeg `ebur128/loudnorm`: 독립 검증용 보조 측정기.
- `DeepFilterNet`: 선택적 보컬 잡음 복원 연구. MIT 또는 Apache-2.0 이중 라이선스.
- `python-audio-separator`: MDX-Net, VR, Demucs, MDXC 계열 모델을 한 인터페이스로 다루는 stem 분리 후보. MIT 라이선스. 모델별 라이선스는 별도 확인한다.
- `noisereduce`: stationary / non-stationary spectral gating 연구 후보. 실제 noise profile이 검출된 경우에만 낮은 강도로 사용한다.

### 참고만 하거나 선택 기능으로 분리

- `Matchering`: 참조곡 기반 frequency response, RMS, peak, stereo width 매칭 아이디어 참고. GPLv3이므로 코드를 직접 포함하기 전에 프로젝트 라이선스 결정 필요.
- `Spotify Pedalboard`: 고품질 오디오 I/O·효과 체인 참고. GPLv3이므로 핵심 의존성 채택 여부를 별도 결정.
- `Demucs`: 원 저장소가 archived 상태이므로 직접 핵심 의존성으로 고정하지 않고, 유지되는 통합 인터페이스나 검증된 모델을 선택적으로 사용한다.

## 7. 개발 순서

### Phase A — 안정화

- 데스크톱 기존 코드 GitHub 이전
- 자동 테스트 실행 가능 구조로 정리
- 5 ms 지연과 tail cut 수정
- 입력·출력 분석 보고서 구현

### Phase B — 채널별 자동화

- Channel Profile Engine
- EQ·압축·스테레오 변화량 제한
- OLD POP / CHILI / Japanese CHILI / Showa 테스트 세트
- 프로필별 A/B 블라인드 평가 기록

### Phase C — 향상 기능

- 노이즈·험·클릭 진단
- Codec Preview
- Reference Assist
- 선택적 vocal repair
- 실험적 stem-aware rescue

### Phase D — 제품화

- PySide6 UI 통합
- 배치 큐, 취소, 재시도, 로그
- 프리셋 버전 관리
- 자동 회귀 테스트와 GitHub Actions
- Windows 실행파일 패키징

## 8. 테스트 통과 기준

- 클리핑 샘플 0
- True Peak가 프로필 ceiling 이하
- 목표 LUFS ±0.20 LU
- 처리 후 잔여 지연 ±1 sample 이내
- 마지막 잔향 절단 없음
- 원본 대비 LRA 감소가 프로필 상한 이하
- 저역 상관관계 안전
- 자동 EQ가 프로필 상한 이하
- NaN, 무한대, 채널 뒤바뀜, 길이 손실 없음
- 동일 입력에 대한 결과 재현 가능
