"""Video assembly service using ffmpeg."""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import VideoAssemblyError


# ---------------------------------------------------------------------------
# Ken Burns motion effects
# ---------------------------------------------------------------------------

MOTION_EFFECTS = [
    # Slow zoom in (center)
    "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Slow zoom out
    "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan left to right
    "zoompan=z='1.3':x='if(lte(on,1),0,min(x+2,iw-iw/zoom))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan right to left
    "zoompan=z='1.3':x='if(lte(on,1),iw-iw/zoom,max(0,x-2))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom in top-left to center
    "zoompan=z='min(zoom+0.0015,1.5)':x='if(lte(on,1),0,min(x+1,iw/2-(iw/zoom/2)))':y='if(lte(on,1),0,min(y+1,ih/2-(ih/zoom/2)))':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom in bottom-right to center
    "zoompan=z='min(zoom+0.0015,1.5)':x='if(lte(on,1),iw-iw/zoom,max(x-1,iw/2-(iw/zoom/2)))':y='if(lte(on,1),ih-ih/zoom,max(y-1,ih/2-(ih/zoom/2)))':d={frames}:s={w}x{h}:fps={fps}",
]


def create_scene_clip(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    duration: float | None = None,
    resolution: tuple[int, int] = (1920, 1080),
    motion: bool = True,
    motion_style: int | None = None,
) -> Path:
    """Create a video clip from a still image and audio.

    Args:
        image_path: Background image.
        audio_path: Narration audio.
        output_path: Output video path.
        duration: Clip duration in seconds.
        resolution: Output resolution.
        motion: If True, apply Ken Burns motion effect.
        motion_style: Specific motion effect index (0-5). Random if None.
    """
    w, h = resolution
    fps = settings.video_fps

    if motion and duration:
        # Apply Ken Burns effect
        frames = int(duration * fps)
        if motion_style is None:
            motion_style = random.randint(0, len(MOTION_EFFECTS) - 1)
        effect = MOTION_EFFECTS[motion_style % len(MOTION_EFFECTS)]
        vf = effect.format(frames=frames, w=w, h=h, fps=fps)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]{vf},format=yuv420p[v]",
            "-map", "[v]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(duration),
            str(output_path),
        ]
    else:
        # Static image (original behavior)
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
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
            "-shortest",
        ]
        if duration:
            cmd.extend(["-t", str(duration)])
        cmd.append(str(output_path))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            if motion:
                # Fallback to static if motion fails
                logger.warning(f"Motion effect failed, falling back to static: {result.stderr[-200:]}")
                return create_scene_clip(
                    image_path, audio_path, output_path,
                    duration=duration, resolution=resolution, motion=False,
                )
            raise VideoAssemblyError(f"Scene clip creation failed: {result.stderr[-500:]}")
        logger.debug(f"Created scene clip: {output_path} (motion={motion})")
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Scene clip creation timed out")


def create_scene_clip_from_video(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    duration: float | None = None,
    resolution: tuple[int, int] = (1920, 1080),
    image_path: Path | None = None,
) -> Path:
    """Create a scene clip using an AI-generated video + narration audio.

    If the video is shorter than the narration, it loops seamlessly.
    The video is slightly slowed down for cinematic feel.
    """
    w, h = resolution

    from autoworker_youtube.services.audio import get_audio_duration
    video_dur = get_audio_duration(video_path)
    target_dur = duration or video_dur
    if video_dur <= 0:
        video_dur = 3.0

    scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"

    # If video is long enough (within 2s), just use it directly
    if video_dur >= target_dur - 2:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]{scale},format=yuv420p[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-crf", str(settings.video_crf),
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(target_dur),
            str(output_path),
        ]
    else:
        # Video is shorter than narration — loop it
        loops = int(target_dur / video_dur) + 2
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loops),
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[0:v]{scale},format=yuv420p[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-crf", str(settings.video_crf),
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(target_dur),
            str(output_path),
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            raise VideoAssemblyError(f"Video clip creation failed: {result.stderr[-500:]}")
        logger.debug(f"Created video-based clip: {output_path} (video={video_dur:.1f}s, target={target_dur:.1f}s)")
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Video clip creation timed out")


# ---------------------------------------------------------------------------
# Concatenation
# ---------------------------------------------------------------------------

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

    # Always re-encode for consistent format across clips
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

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise VideoAssemblyError(f"Concatenation failed: {result.stderr[-500:]}")

        list_path.unlink(missing_ok=True)
        logger.info(f"Concatenated {len(clip_paths)} clips -> {output_path}")
        return output_path
    except subprocess.TimeoutExpired:
        raise VideoAssemblyError("Video concatenation timed out")


# ---------------------------------------------------------------------------
# Subtitles
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# BGM
# ---------------------------------------------------------------------------

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
