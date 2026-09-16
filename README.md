# HARU Mastering v3.9

`HARU Mastering v3.9` separates channel/mastering presets from real music genres and replaces the v3.8 fixed 5-step Fullness retry ladder with a faster guarded engine.

Executable:

`Suno15_Mastering_v3_9.pyw`

Window title:

`HARU / SUNO 15-SET MASTERING v3.9`

## Run

Use `RUN.bat` or `START_HERE.bat`.

`RUN.bat` starts files in this order:

1. `Suno15_Mastering_v3_9.pyw`
2. `Suno15_Mastering_v3_8_1.pyw`
3. `Suno15_Mastering_v3_8.pyw`
4. Earlier v3 adapters
5. v2
6. legacy compatibility module

`Suno15_Mastering.pyw` remains as the legacy import compatibility module. If it is double-clicked directly, it shows a notice and redirects to the latest HARU Mastering.

## Channel Presets

Channel presets set the broad sound direction: target LUFS tendency, true-peak safety, listening fatigue, warmth, saturation, stereo tendency, vocal texture and default Fullness behavior.

- 올드팝 라운지
- 한국 시니어
- 일본 시니어
- Tokyo Chill / 일본 20~30대
- 일반 / 채널 지정 없음

`OLD POP LOUNGE` is a channel/mastering preset. It is not a music genre.

## Music Genres

Genres describe the music itself: EQ tendency, dynamics and instrument/vocal behavior.

- 팝
- 발라드
- 재즈
- 샹송
- 소울
- R&B
- 포크 / 어쿠스틱
- 록 / 밴드
- 시티팝
- 엔카 / 가요곡
- 트로트
- K-POP
- 동요 / Kids Pop
- Lo-fi
- Chill Rap
- Instrumental / New Age
- 60~80s Pop / Oldies
- 기타 / 일반

## Profile Composition

Final mastering uses:

`CHANNEL PROFILE + GENRE PROFILE + SOUND MODE`

Example:

`올드팝 라운지 + 발라드 + 풍부함+`

This combines long-listening Old Pop Lounge behavior, ballad dynamics/EQ and Fullness processing.

## Fast Fullness Engine

v3.8 could try:

`100 -> 75 -> 50 -> 25 -> OFF`

v3.9 uses:

- FAST: Fullness maximum 1 render pass
- QUALITY+: Fullness maximum 2 render passes
- Retry strength is selected from the failure reason
- Codec Preview is not run for every Fullness candidate
- Codec Preview runs on the final candidate path
- Codec unsafe cases still use the loudness-preserving lower-ceiling rerender strategy

## Stage Timing

Each track logs internal stages:

- analysis
- base mastering
- Fullness analysis
- Fullness render
- Quality Gate
- Codec Preview
- complete time

## Preserved Safety Features

- final LUFS
- True Peak
- final LRA
- Dynamics Guard
- Smart Delay
- Adaptive Tail
- low-band stereo correlation
- clipping 0
- codec safety
- RELEASE_READY / NEEDS_REVIEW
- Fullness
- final CSV sync
- suffixless final WAV names

## Verify

Run:

```powershell
pytest
```

Launcher and v3.9 checks:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_v39_app.py
.\.venv\Scripts\python.exe .\scripts\verify_v38_launch_paths.py
```

Synthetic benchmark:

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_v39_synthetic.py
```

Do not merge this branch to `main` until the user verifies 15 real Suno WAV files.

