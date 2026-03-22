"""Audio processing service."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not get duration for {audio_path}: {e}")
        return 5.0  # default fallback


def get_all_durations(audio_files: list[Path]) -> list[float]:
    """Get durations for multiple audio files."""
    return [get_audio_duration(f) for f in audio_files]


def mix_audio(
    narration_path: Path,
    bgm_path: Path | None,
    output_path: Path,
    bgm_volume_db: float = -15.0,
) -> Path:
    """Mix narration with background music."""
    if bgm_path is None or not bgm_path.exists():
        # No BGM, just copy narration
        import shutil
        shutil.copy2(narration_path, output_path)
        return output_path

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(narration_path),
                "-i", str(bgm_path),
                "-filter_complex",
                f"[1:a]volume={bgm_volume_db}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first",
                "-ac", "2",
                str(output_path),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return output_path
    except subprocess.CalledProcessError as e:
        logger.warning(f"Audio mixing failed, using narration only: {e}")
        import shutil
        shutil.copy2(narration_path, output_path)
        return output_path


def concatenate_audio(audio_files: list[Path], output_path: Path) -> Path:
    """Concatenate multiple audio files into one."""
    if not audio_files:
        raise ValueError("No audio files to concatenate")

    if len(audio_files) == 1:
        import shutil
        shutil.copy2(audio_files[0], output_path)
        return output_path

    # Create concat file list
    list_path = output_path.parent / "audio_concat_list.txt"
    with open(list_path, "w") as f:
        for af in audio_files:
            f.write(f"file '{af.resolve()}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(output_path),
        ],
        capture_output=True,
        timeout=60,
        check=True,
    )

    list_path.unlink(missing_ok=True)
    return output_path
