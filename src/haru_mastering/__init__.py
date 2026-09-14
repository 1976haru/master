"""HARU Mastering safety and analysis core."""

from .analysis import AudioMetrics, analyze_array, analyze_file
from .alignment import compensate_delay, estimate_delay_samples, pad_tail, trim_padded_tail
from .filenames import final_output_candidates, final_output_name, final_output_path, find_final_output
from .profiles import load_profiles, resolve_profile
from .version import APP_TITLE, REPORT_VERSION, VERSION

__all__ = [
    "AudioMetrics",
    "APP_TITLE",
    "REPORT_VERSION",
    "VERSION",
    "analyze_array",
    "analyze_file",
    "compensate_delay",
    "estimate_delay_samples",
    "final_output_candidates",
    "final_output_name",
    "final_output_path",
    "find_final_output",
    "load_profiles",
    "pad_tail",
    "resolve_profile",
    "trim_padded_tail",
]
