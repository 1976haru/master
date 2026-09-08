# HARU Mastering

Windows 10/11용 오프라인 배치 마스터링·음원 향상 프로그램입니다.

## 목표

- 원본을 덮어쓰지 않는 안전한 WAV/MP3 배치 처리
- LUFS-I, True Peak, LRA, Crest Factor, Stereo Correlation 기반 분석
- 채널별 사운드 정체성을 반영한 마스터링 프로필
- 처리 전후 A/B 비교와 자동 품질검사(Quality Gate)
- 48 kHz / 24-bit WAV 중심의 스트리밍 안전 출력

## 채널 프로필

- `old_pop_lounge`: 따뜻하고 성숙하며 장시간 들어도 피곤하지 않은 사운드
- `old_pop_lounge_french_chanson`: 프랑스어 자음·모음과 대화형 보컬을 보존하는 샹송 프로필
- `chili_lab`: 가까운 보컬, 타이트한 저역, 도시적인 Chill Rap / Urban Soul
- `chili_lab_ja`: 일본어 모라 리듬과 발음 명료도를 보존하는 일본어 CHILI LAB
- `showa_seventies`: 1970년대 일본 New Music·포크·가요의 절제된 중저역과 부드러운 고역

## v2 핵심 방향

1. 분석 우선: 입력 상태를 측정한 뒤 필요한 처리만 적용
2. 채널별 프로필: 모든 곡에 같은 EQ·압축을 적용하지 않음
3. 변화량 제한: 자동 EQ·스테레오·컴프레션을 작은 범위로 제한
4. 지연 보상: 룩어헤드·STFT 처리 지연을 샘플 단위로 보상
5. 꼬리 보존: 처리 전 tail padding 후 렌더링하여 잔향 절단 방지
6. 출력 검증: LUFS, True Peak, 클리핑, 위상, 시작 지연, 마지막 꼬리 자동 검사

## 저장소 운영

- `main`: 검증된 안정 버전
- `upgrade/*`: 기능 개발 브랜치
- 모든 큰 변경은 Pull Request로 비교 후 병합
- 음원 원본, 출력 WAV, 모델 파일, 가상환경, API 키는 Git에 올리지 않음

## 현재 상태

저장소 초기화 단계입니다. 데스크톱의 기존 프로그램 소스를 가져온 뒤 채널 프로필 엔진과 품질검사 모듈을 연결합니다.
