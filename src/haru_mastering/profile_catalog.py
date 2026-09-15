from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ChannelProfile:
    key: str
    label: str
    profile_name: str
    target_lufs_i: float
    true_peak_ceiling_dbtp: float
    target_lra: float
    max_lra_reduction_lu: float
    compression_scale: float
    saturation_max_wet_percent: float
    density_max_wet_percent: float
    warmth_scale: float
    body_scale: float
    character: str
    default_fullness_strength_percent: int = 100
    max_projected_peak_reduction_db: float = 1.5
    maximum_loudness_concession_lu: float = 2.0
    compression_transparent_margin_lu: float = 0.5
    compression_reduced_margin_lu: float = 1.0
    compression_reduced_scale: float = 0.35
    peak_stressed_max_projected_reduction_db: float = 0.8
    absolute_minimum_safety_target_lufs_i: float = -18.0
    true_peak_safety_margin_db: float = 0.05

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GenreProfile:
    key: str
    label: str
    base_key: str
    target_lra: float
    eq: tuple[str, ...]
    comp: tuple[float, float, float, float, float]
    character: str
    saturation_max_wet_percent: float
    density_max_wet_percent: float
    max_lra_reduction_lu: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CHANNEL_PROFILES: dict[str, ChannelProfile] = {
    "OLD_POP_LOUNGE": ChannelProfile(
        key="OLD_POP_LOUNGE",
        label="올드팝 라운지",
        profile_name="old_pop_lounge",
        target_lufs_i=-14.0,
        true_peak_ceiling_dbtp=-1.5,
        target_lra=11.0,
        max_lra_reduction_lu=0.60,
        compression_scale=0.88,
        saturation_max_wet_percent=6.0,
        density_max_wet_percent=5.0,
        warmth_scale=1.00,
        body_scale=1.00,
        character="따뜻함, 편안함, 장시간 청취, 과한 광택 금지",
    ),
    "SENIOR_KR": ChannelProfile(
        key="SENIOR_KR",
        label="한국 시니어",
        profile_name="old_pop_lounge",
        target_lufs_i=-14.2,
        true_peak_ceiling_dbtp=-1.5,
        target_lra=10.0,
        max_lra_reduction_lu=0.60,
        compression_scale=0.82,
        saturation_max_wet_percent=5.0,
        density_max_wet_percent=4.0,
        warmth_scale=0.95,
        body_scale=0.95,
        character="성숙한 한국어 보컬, 부드러운 고역, 낮은 청취 피로도",
    ),
    "SENIOR_JP": ChannelProfile(
        key="SENIOR_JP",
        label="일본 시니어",
        profile_name="showa_seventies",
        target_lufs_i=-14.3,
        true_peak_ceiling_dbtp=-1.5,
        target_lra=11.0,
        max_lra_reduction_lu=0.55,
        compression_scale=0.78,
        saturation_max_wet_percent=4.0,
        density_max_wet_percent=3.0,
        warmth_scale=0.90,
        body_scale=0.90,
        character="일본 시니어용 성숙한 보컬, 잔잔한 고역, 자연스러운 공간",
    ),
    "TOKYO_CHILL": ChannelProfile(
        key="TOKYO_CHILL",
        label="Tokyo Chill / 일본 20~30대",
        profile_name="chili_lab_ja",
        target_lufs_i=-14.0,
        true_peak_ceiling_dbtp=-1.2,
        target_lra=9.0,
        max_lra_reduction_lu=0.80,
        compression_scale=1.00,
        saturation_max_wet_percent=4.0,
        density_max_wet_percent=3.0,
        warmth_scale=0.80,
        body_scale=0.85,
        character="현대적인 Chill 성향, 타이트한 저역, 과하지 않은 선명도",
    ),
    "GENERAL": ChannelProfile(
        key="GENERAL",
        label="일반 / 채널 지정 없음",
        profile_name="old_pop_lounge",
        target_lufs_i=-14.0,
        true_peak_ceiling_dbtp=-1.5,
        target_lra=10.0,
        max_lra_reduction_lu=0.80,
        compression_scale=0.92,
        saturation_max_wet_percent=3.0,
        density_max_wet_percent=2.0,
        warmth_scale=0.80,
        body_scale=0.80,
        character="특정 채널 색을 최소화한 중립적 안전 마스터",
    ),
}


GENRE_PROFILES: dict[str, GenreProfile] = {
    "POP": GenreProfile(
        "POP",
        "팝",
        "POP",
        9.0,
        (
            "highpass=f=27",
            "equalizer=f=100:t=q:w=0.9:g=0.3",
            "equalizer=f=280:t=q:w=1.0:g=-0.4",
            "equalizer=f=3200:t=q:w=1.0:g=0.5",
        ),
        (0.17, 1.42, 23.0, 230.0, 1.03),
        "보컬과 훅의 균형, 정돈된 저역, 선명하지만 피곤하지 않은 팝",
        3.0,
        2.0,
        0.80,
    ),
    "BALLAD": GenreProfile(
        "BALLAD",
        "발라드",
        "BALLAD",
        10.0,
        (
            "highpass=f=25",
            "equalizer=f=250:t=q:w=1.0:g=-0.4",
            "equalizer=f=3000:t=q:w=1.0:g=0.5",
            "equalizer=f=8500:t=q:w=1.0:g=-0.3",
        ),
        (0.18, 1.35, 30.0, 280.0, 1.03),
        "감정과 호흡 보존, 피아노와 스트링의 자연스러운 깊이",
        5.0,
        4.0,
        0.80,
    ),
    "JAZZ": GenreProfile(
        "JAZZ",
        "재즈",
        "JAZZ",
        13.0,
        (
            "highpass=f=22",
            "equalizer=f=220:t=q:w=1.0:g=-0.2",
            "equalizer=f=4500:t=q:w=1.0:g=0.2",
        ),
        (0.22, 1.18, 40.0, 320.0, 1.00),
        "다이내믹 보존, 피아노/베이스/브러시 질감",
        2.0,
        1.0,
        0.50,
    ),
    "CHANSON": GenreProfile(
        "CHANSON",
        "샹송",
        "CHANSON",
        11.0,
        (
            "highpass=f=24",
            "equalizer=f=240:t=q:w=1.0:g=-0.3",
            "equalizer=f=2600:t=q:w=1.0:g=0.6",
            "equalizer=f=8000:t=q:w=1.0:g=-0.4",
        ),
        (0.19, 1.30, 32.0, 300.0, 1.02),
        "둥근 모음, 대화형 보컬, 어쿠스틱 악기 질감",
        4.0,
        3.0,
        0.50,
    ),
    "SOUL": GenreProfile(
        "SOUL",
        "소울",
        "SOUL",
        10.0,
        (
            "highpass=f=24",
            "equalizer=f=110:t=q:w=0.9:g=0.4",
            "equalizer=f=350:t=q:w=1.0:g=0.2",
            "equalizer=f=3000:t=q:w=1.0:g=0.5",
            "equalizer=f=8500:t=q:w=1.0:g=-0.2",
        ),
        (0.17, 1.40, 26.0, 250.0, 1.04),
        "두꺼운 보컬, 따뜻한 중역, 드럼 펀치",
        6.0,
        5.0,
        0.80,
    ),
    "R&B": GenreProfile(
        "R&B",
        "R&B",
        "R&B",
        10.0,
        (
            "highpass=f=25",
            "equalizer=f=90:t=q:w=0.8:g=0.5",
            "equalizer=f=260:t=q:w=1.0:g=-0.5",
            "equalizer=f=3200:t=q:w=1.0:g=0.5",
        ),
        (0.17, 1.45, 24.0, 230.0, 1.04),
        "킥과 베이스의 탄력, 보컬 선명도, 저중역 혼탁 억제",
        5.0,
        3.0,
        0.90,
    ),
    "FOLK_ACOUSTIC": GenreProfile(
        "FOLK_ACOUSTIC",
        "포크 / 어쿠스틱",
        "ACOUSTIC",
        12.0,
        (
            "highpass=f=22",
            "equalizer=f=240:t=q:w=1.0:g=-0.2",
            "equalizer=f=3500:t=q:w=1.0:g=0.2",
        ),
        (0.22, 1.18, 40.0, 340.0, 1.00),
        "기타와 생악기 질감, 보컬 호흡, 넓은 다이내믹",
        2.0,
        1.0,
        0.50,
    ),
    "ROCK": GenreProfile(
        "ROCK",
        "록 / 밴드",
        "ROCK",
        9.0,
        (
            "highpass=f=27",
            "equalizer=f=100:t=q:w=0.9:g=0.4",
            "equalizer=f=300:t=q:w=1.0:g=-0.4",
            "equalizer=f=2800:t=q:w=1.0:g=0.4",
            "equalizer=f=8500:t=q:w=1.0:g=-0.1",
        ),
        (0.16, 1.48, 18.0, 220.0, 1.04),
        "드럼과 기타 에너지, 보컬 중심, 트랜지언트 보존",
        3.0,
        2.0,
        0.80,
    ),
    "CITY_POP": GenreProfile(
        "CITY_POP",
        "시티팝",
        "CITY POP JP",
        10.0,
        (
            "highpass=f=25",
            "equalizer=f=90:t=q:w=0.9:g=0.4",
            "equalizer=f=300:t=q:w=1.0:g=-0.3",
            "equalizer=f=3000:t=q:w=1.0:g=0.4",
            "equalizer=f=9000:t=q:w=1.0:g=0.2",
        ),
        (0.18, 1.34, 28.0, 260.0, 1.02),
        "도시적인 베이스와 키보드, 부드러운 빈티지 광택",
        4.0,
        3.0,
        0.80,
    ),
    "ENKA_KAYOKYOKU": GenreProfile(
        "ENKA_KAYOKYOKU",
        "엔카 / 가요곡",
        "ENKA JP",
        10.0,
        (
            "highpass=f=24",
            "equalizer=f=180:t=q:w=0.9:g=0.3",
            "equalizer=f=360:t=q:w=1.0:g=-0.2",
            "equalizer=f=2500:t=q:w=1.0:g=0.4",
            "equalizer=f=7000:t=q:w=1.0:g=-0.5",
        ),
        (0.20, 1.25, 34.0, 320.0, 1.01),
        "깊은 보컬과 비브라토, 선명한 가사, 과하지 않은 고역",
        4.0,
        3.0,
        0.60,
    ),
    "TROT": GenreProfile(
        "TROT",
        "트로트",
        "TROT KR",
        9.0,
        (
            "highpass=f=27",
            "equalizer=f=110:t=q:w=0.9:g=0.3",
            "equalizer=f=300:t=q:w=1.0:g=-0.3",
            "equalizer=f=2800:t=q:w=1.0:g=0.6",
            "equalizer=f=7200:t=q:w=1.0:g=-0.2",
        ),
        (0.17, 1.42, 24.0, 240.0, 1.03),
        "또렷한 한국어 보컬, 리듬 추진력, 편안한 고역",
        4.0,
        3.0,
        0.80,
    ),
    "K_POP": GenreProfile(
        "K_POP",
        "K-POP",
        "K-POP",
        9.0,
        (
            "highpass=f=28",
            "equalizer=f=90:t=q:w=0.8:g=0.5",
            "equalizer=f=260:t=q:w=1.0:g=-0.6",
            "equalizer=f=3300:t=q:w=1.0:g=0.7",
            "equalizer=f=9000:t=q:w=1.0:g=0.2",
        ),
        (0.16, 1.50, 20.0, 210.0, 1.04),
        "선명한 보컬과 훅, 타이트한 킥/베이스, 넓은 공간감",
        3.0,
        2.0,
        0.90,
    ),
    "KIDS_POP": GenreProfile(
        "KIDS_POP",
        "동요 / Kids Pop",
        "KIDS POP",
        8.0,
        (
            "highpass=f=30",
            "equalizer=f=180:t=q:w=1.0:g=-0.2",
            "equalizer=f=3000:t=q:w=1.0:g=0.5",
            "equalizer=f=7500:t=q:w=1.0:g=-0.3",
        ),
        (0.18, 1.35, 22.0, 220.0, 1.02),
        "어린이 보컬 명료도, 밝지만 자극적이지 않은 고역",
        2.0,
        1.5,
        0.80,
    ),
    "LOFI": GenreProfile(
        "LOFI",
        "Lo-fi",
        "LOFI",
        10.0,
        (
            "highpass=f=25",
            "equalizer=f=120:t=q:w=0.9:g=0.2",
            "equalizer=f=320:t=q:w=1.0:g=-0.2",
            "equalizer=f=6500:t=q:w=1.0:g=-0.4",
        ),
        (0.21, 1.20, 34.0, 320.0, 1.01),
        "잔잔한 질감, 따뜻한 저중역, 부드러운 트랜지언트",
        3.0,
        2.0,
        0.70,
    ),
    "CHILL_RAP": GenreProfile(
        "CHILL_RAP",
        "Chill Rap",
        "CHILI EN",
        9.0,
        (
            "highpass=f=25",
            "equalizer=f=85:t=q:w=0.8:g=0.6",
            "equalizer=f=250:t=q:w=1.0:g=-0.6",
            "equalizer=f=3000:t=q:w=1.0:g=0.6",
            "equalizer=f=9000:t=q:w=1.0:g=0.2",
        ),
        (0.16, 1.50, 22.0, 220.0, 1.04),
        "가까운 보컬, 타이트한 저역, 도시적 Chill 무드",
        4.0,
        3.0,
        0.80,
    ),
    "INSTRUMENTAL": GenreProfile(
        "INSTRUMENTAL",
        "Instrumental / New Age",
        "INSTRUMENTAL",
        12.0,
        (
            "highpass=f=22",
            "equalizer=f=250:t=q:w=1.0:g=-0.2",
            "equalizer=f=4200:t=q:w=1.0:g=0.2",
        ),
        (0.23, 1.15, 42.0, 350.0, 1.00),
        "피아노와 연주 악기 다이내믹, 잔향과 공간 보존",
        2.0,
        1.0,
        0.50,
    ),
    "OLDIES_60S_80S": GenreProfile(
        "OLDIES_60S_80S",
        "60~80s Pop / Oldies",
        "OLD POP",
        11.0,
        (
            "highpass=f=24",
            "equalizer=f=260:t=q:w=1.0:g=-0.3",
            "equalizer=f=3000:t=q:w=1.0:g=0.5",
            "equalizer=f=8500:t=q:w=1.0:g=-0.2",
        ),
        (0.18, 1.30, 30.0, 280.0, 1.02),
        "60~80년대 팝의 보컬 중심 구조와 자연스러운 빈티지 밸런스",
        5.0,
        4.0,
        0.60,
    ),
    "GENERAL": GenreProfile(
        "GENERAL",
        "기타 / 일반",
        "GENERAL",
        10.0,
        (
            "highpass=f=25",
            "equalizer=f=280:t=q:w=1.0:g=-0.2",
            "equalizer=f=3200:t=q:w=1.0:g=0.2",
        ),
        (0.20, 1.22, 32.0, 300.0, 1.01),
        "특정 장르에 치우치지 않는 중립적 음색",
        3.0,
        2.0,
        0.80,
    ),
}

CHANNEL_DISPLAY_ORDER = (
    "OLD_POP_LOUNGE",
    "SENIOR_KR",
    "SENIOR_JP",
    "TOKYO_CHILL",
    "GENERAL",
)

GENRE_DISPLAY_ORDER = (
    "POP",
    "BALLAD",
    "JAZZ",
    "CHANSON",
    "SOUL",
    "R&B",
    "FOLK_ACOUSTIC",
    "ROCK",
    "CITY_POP",
    "ENKA_KAYOKYOKU",
    "TROT",
    "K_POP",
    "KIDS_POP",
    "LOFI",
    "CHILL_RAP",
    "INSTRUMENTAL",
    "OLDIES_60S_80S",
    "GENERAL",
)

DEFAULT_CHANNEL_KEY = "OLD_POP_LOUNGE"
DEFAULT_GENRE_KEY = "POP"
DEFAULT_SOUND_MODE = "RICH"


def composite_key(channel_key: str, genre_key: str) -> str:
    channel = normalize_channel_key(channel_key)
    genre = normalize_genre_key(genre_key)
    return f"CG_{channel}__{genre}"


def normalize_channel_key(channel_key: str | None) -> str:
    key = str(channel_key or DEFAULT_CHANNEL_KEY).strip().upper()
    return key if key in CHANNEL_PROFILES else DEFAULT_CHANNEL_KEY


def normalize_genre_key(genre_key: str | None) -> str:
    key = str(genre_key or DEFAULT_GENRE_KEY).strip().upper()
    return key if key in GENRE_PROFILES else "GENERAL"


def _scaled_comp(
    comp: tuple[float, float, float, float, float],
    *,
    compression_scale: float,
) -> list[float]:
    threshold, ratio, attack, release, makeup = comp
    scaled_ratio = 1.0 + (float(ratio) - 1.0) * float(compression_scale)
    return [
        float(threshold),
        round(scaled_ratio, 3),
        float(attack),
        float(release),
        float(makeup),
    ]


def compose_legacy_genre(channel_key: str, genre_key: str) -> dict[str, Any]:
    channel = CHANNEL_PROFILES[normalize_channel_key(channel_key)]
    genre = GENRE_PROFILES[normalize_genre_key(genre_key)]
    target_lra = round((channel.target_lra * 0.55) + (genre.target_lra * 0.45), 1)
    return {
        "label": f"{channel.label} + {genre.label}",
        "target_i": float(channel.target_lufs_i),
        "target_tp": float(channel.true_peak_ceiling_dbtp),
        "target_lra": float(target_lra),
        "eq": list(genre.eq),
        "comp": _scaled_comp(genre.comp, compression_scale=channel.compression_scale),
        "character": f"{channel.character} + {genre.character}",
        "channel_key": channel.key,
        "genre_key": genre.key,
    }


def compose_runtime_profile(
    base_profile: Mapping[str, Any],
    channel_key: str,
    genre_key: str,
) -> dict[str, Any]:
    channel = CHANNEL_PROFILES[normalize_channel_key(channel_key)]
    genre = GENRE_PROFILES[normalize_genre_key(genre_key)]
    profile = copy.deepcopy(dict(base_profile))
    profile["label"] = f"{channel.label} + {genre.label}"
    profile["targetLufsI"] = float(channel.target_lufs_i)
    profile["configuredTargetLufsI"] = float(channel.target_lufs_i)
    profile["minimumTargetLufsI"] = float(
        channel.target_lufs_i - channel.maximum_loudness_concession_lu
    )
    profile["maxProjectedPeakReductionDb"] = float(channel.max_projected_peak_reduction_db)
    profile["maximumLoudnessConcessionLu"] = float(channel.maximum_loudness_concession_lu)
    profile["compressionTransparentMarginLu"] = float(channel.compression_transparent_margin_lu)
    profile["compressionReducedMarginLu"] = float(channel.compression_reduced_margin_lu)
    profile["compressionReducedScale"] = float(channel.compression_reduced_scale)
    profile["peakStressedMaxProjectedPeakReductionDb"] = float(
        channel.peak_stressed_max_projected_reduction_db
    )
    profile["absoluteMinimumSafetyTargetLufsI"] = float(
        channel.absolute_minimum_safety_target_lufs_i
    )
    profile["truePeakSafetyMarginDb"] = float(channel.true_peak_safety_margin_db)
    profile["truePeakCeilingDbtp"] = float(channel.true_peak_ceiling_dbtp)
    profile["maxLraReductionLu"] = float(
        min(channel.max_lra_reduction_lu, genre.max_lra_reduction_lu)
    )
    profile["profileName"] = composite_key(channel.key, genre.key)
    profile["channelProfileKey"] = channel.key
    profile["genreProfileKey"] = genre.key
    profile["intent"] = [channel.character, genre.character]
    profile["fullness"] = {
        "defaultStrengthPercent": int(channel.default_fullness_strength_percent),
        "saturationMaximumWetPercent": float(
            min(channel.saturation_max_wet_percent, genre.saturation_max_wet_percent)
        ),
        "densityMaximumWetPercent": float(
            min(channel.density_max_wet_percent, genre.density_max_wet_percent)
        ),
        "warmthScale": float(channel.warmth_scale),
        "bodyScale": float(channel.body_scale),
    }
    return profile
