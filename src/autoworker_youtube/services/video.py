"""Video assembly service using ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import VideoAssemblyError


def create_scene_clip(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    duration: float | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> Path:
    """Create a video clip from a still image and audio."""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio=decrease,pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2",
        "-shortest",
    ]

    if duration:
        cmd.extend(["-t", str(duration)])

    cmd.append(str(output_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise VideoAssemblyError(f"Scene clip creation failed: {result.stderr[-500:]}")
        logger.debug(f"Created scene clip: {output_path}")
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Scene clip creation timed out")


def concatenate_clips(
    clip_paths: list[Path],
    output_path: Path,
) -> Path:
    """Concatenate multiple video clips into one final video."""
    if not clip_paths:
        raise VideoAssemblyError("No clips to concatenate")

    # Create concat file
    list_path = output_path.parent / "concat_list.txt"
    with open(list_path, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-c", "copy",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            # If copy fails, try re-encoding
            logger.warning("Concat copy failed, re-encoding...")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_path),
                "-c:v", "libx264",
                "-crf", str(settings.video_crf),
                "-c:a", "aac",
                "-b:a", "192k",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise VideoAssemblyError(f"Concatenation failed: {result.stderr[-500:]}")

        list_path.unlink(missing_ok=True)
        logger.info(f"Concatenated {len(clip_paths)} clips -> {output_path}")
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Video concatenation timed out")


def _find_korean_font_name() -> str:
    """Find an available Korean font name for FFmpeg subtitles."""
    candidates = [
        ("NanumSquare", "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"),
        ("NanumSquareRound", "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"),
        ("NanumGothic", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
        ("Noto Sans CJK KR", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    ]
    for name, path in candidates:
        if Path(path).exists():
            return name
    return "NanumGothic"


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    font_size: int = 24,
) -> Path:
    """Burn subtitles into video."""
    # Escape special characters in path for ffmpeg filter
    srt_escaped = str(srt_path).replace("\\", "\\\\").replace(":", "\\:")
    font_name = _find_korean_font_name()

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles='{srt_escaped}':force_style='FontName={font_name},FontSize={font_size},PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,MarginV=50'",
        "-c:v", "libx264",
        "-crf", str(settings.video_crf),
        "-c:a", "copy",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.warning(f"Subtitle burn failed, returning video without subtitles: {result.stderr[-300:]}")
            import shutil
            shutil.copy2(video_path, output_path)
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Subtitle burning timed out")


def add_bgm(
    video_path: Path,
    bgm_path: Path,
    output_path: Path,
    bgm_volume_db: float = -15.0,
) -> Path:
    """Add background music to video."""
    if not bgm_path.exists():
        import shutil
        shutil.copy2(video_path, output_path)
        return output_path

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(bgm_path),
        "-filter_complex",
        f"[1:a]volume={bgm_volume_db}dB,aloop=loop=-1:size=2e+09[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.warning("BGM addition failed, returning video without BGM")
            import shutil
            shutil.copy2(video_path, output_path)
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("BGM addition timed out")
