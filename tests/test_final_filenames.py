from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from haru_mastering.analysis import analyze_file
from haru_mastering.filenames import final_output_name, final_output_path, find_final_output


def _write_wav(path: Path) -> None:
    sample_rate = 48000
    t = np.arange(sample_rate, dtype=np.float64) / sample_rate
    mono = 0.05 * np.sin(2.0 * np.pi * 440.0 * t)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.column_stack((mono, mono)), sample_rate, subtype="PCM_24")


def test_final_output_name_keeps_original_stem():
    assert final_output_name("01. Test Song.wav") == "01. Test Song.wav"
    assert (
        final_output_name("01. Honey on the Knife (꿀 묻은 버터나이프).wav")
        == "01. Honey on the Knife (꿀 묻은 버터나이프).wav"
    )


def test_forbidden_master_suffixes_are_not_final_names():
    name = final_output_name("01. Test Song.wav")
    forbidden = ("_MASTER.wav", "_master.wav", "_MATER.wav", "_MASTERED.wav")
    assert not any(name.endswith(suffix) for suffix in forbidden)


def test_release_ready_suffixless_file_is_found_for_metrics(tmp_path):
    track = "01. Test Song.wav"
    final = tmp_path / "01_RELEASE_READY" / track
    _write_wav(final)

    found = find_final_output(tmp_path, track)
    assert found == final
    metrics = analyze_file(found)
    assert np.isfinite(metrics.lufs_i)
    assert np.isfinite(metrics.true_peak_dbtp)
    assert np.isfinite(metrics.lra_lu)


def test_needs_review_suffixless_file_is_found_for_metrics(tmp_path):
    track = "02. Problem Song.wav"
    final = tmp_path / "02_NEEDS_REVIEW" / track
    _write_wav(final)

    found = find_final_output(tmp_path, track)
    assert found == final
    metrics = analyze_file(found)
    assert np.isfinite(metrics.lufs_i)
    assert np.isfinite(metrics.true_peak_dbtp)
    assert np.isfinite(metrics.lra_lu)


def test_source_file_is_not_the_output_path(tmp_path):
    source = tmp_path / "01. Test Song.wav"
    out_dir = tmp_path / "MASTER_OLD_POP_AUTO_20260914_000000"
    _write_wav(source)
    before = source.read_bytes()

    output = final_output_path(out_dir, source)

    assert output.name == source.name
    assert output != source
    assert source.read_bytes() == before
