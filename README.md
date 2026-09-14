# HARU Mastering v3.8 FULLNESS ENGINE

`HARU Mastering v3.8 - FULLNESS ENGINE` is the v3.8 development version. It keeps the v3.7.2 multi-genre UI, codec ceiling rerender, final LUFS/LRA/CSV sync, and Quality Gate, then adds analysis-driven warmth and density without raising the target LUFS.

Executable:

`Suno15_Mastering_v3_8.pyw`

Window title:

`HARU / SUNO 15-SET MASTERING v3.8 - FULLNESS ENGINE`

## Run

Use `RUN.bat` or `START_HERE.bat`.

`RUN.bat` starts files in this order:

1. `Suno15_Mastering_v3_8.pyw`
2. `Suno15_Mastering_v3_7_2.pyw`
3. Earlier v3 adapters
4. v2
5. legacy compatibility module

`Suno15_Mastering.pyw` remains as the legacy import compatibility module. If it is double-clicked directly, it shows a notice and redirects to the latest HARU Mastering instead of opening the v1.1 UI.

The old package folder is archived at `archive/legacy_v1_2`. Its `RUN.bat` and `START_HERE.bat` also forward to the root `RUN.bat`.

## Fullness Engine

Fullness Engine does not solve fullness by making the song louder. OLD POP still keeps the `-14.0 LUFS` target. The engine analyzes each track and applies only the needed amount of:

- Warmth: 90-220 Hz, max `+0.8 dB`
- Body: 220-450 Hz, max `+0.5 dB`
- Warm saturation: tanh soft saturation with dry/wet blend
- Parallel density: very light center density
- Auto Guard: `100% -> 75% -> 50% -> 25% -> OFF`

Guarded conditions:

- clipping 0
- True Peak ceiling
- LUFS tolerance `0.20 LU`
- LRA and Dynamics Guard
- low-band stereo correlation below 110 Hz
- codec preview safety
- Tail safety

## Sound Mode

The UI adds `사운드 성향` under quality mode:

- `자연스러움`: bypasses Fullness DSP
- `풍부함+ (추천)`: applies automatic Warmth / Harmonic / Density only as needed

Default `풍부함+`: OLD POP, SENIOR KR, SENIOR JP, SHOWA JP, BALLAD, SOUL, K-POP, KIDS POP.

Default `자연스러움`: JAZZ, ACOUSTIC, INSTRUMENTAL.

## CSV Columns

`mastering_report.csv` and `03_REPORT/mastering_report.csv` include:

- `app_version`
- `fullness_mode`
- `fullness_strength_percent`
- `warmth_gain_db`
- `body_gain_db`
- `saturation_wet_percent`
- `density_wet_percent`
- `fullness_auto_reduced`
- `fullness_retry_count`
- `fullness_bypassed_reason`

## Preserved v3.7.2 Features

- 23 genres
- OLD POP, Korean Senior, Japanese Senior, SHOWA, Enka, K-POP, Kids Pop, General
- Smart Delay
- Adaptive Tail
- Dynamics Guard
- codec ceiling rerender
- final LUFS sync
- `final_LRA`
- `final_lufs_within_tolerance`
- `RELEASE_READY` / `NEEDS_REVIEW`
- HTML / JSON / CSV report
- 48 kHz PCM24 output
- clipping 0 protection

## Verify

Run:

```powershell
pytest
```

Launcher and v3.8 checks:

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_v38_app.py
.\.venv\Scripts\python.exe .\scripts\verify_v38_launch_paths.py
```

Do not merge this branch to `main` until the user verifies 15 real Suno WAV files.
