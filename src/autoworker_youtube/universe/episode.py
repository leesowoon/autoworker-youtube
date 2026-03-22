"""Episode definition and generation for the Bori Universe."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.services import audio, subtitle, tts, video
from autoworker_youtube.universe.renderer import UniverseRenderer
from autoworker_youtube.universe.world import BoriUniverse


def load_episode(episode_path: Path) -> dict:
    """Load an episode definition from JSON file."""
    with open(episode_path, encoding="utf-8") as f:
        return json.load(f)


def generate_episode(
    episode_data: dict,
    output_dir: Path,
    output_path: Path | None = None,
    universe: BoriUniverse | None = None,
    animate: bool = True,
    voice: str = "ko-KR-SunHiNeural",
    voice_rate: str = "-15%",
) -> Path | None:
    """Generate a complete episode video from episode definition.

    Args:
        episode_data: Episode definition dict with title, scenes, etc.
        output_dir: Working directory for intermediate files.
        output_path: Final video output path.
        universe: BoriUniverse instance (creates default if None).
        animate: Whether to generate animated videos with Grok I2V.
        voice: TTS voice ID.
        voice_rate: TTS speed adjustment.

    Returns:
        Path to the generated video file.
    """
    universe = universe or BoriUniverse()
    renderer = UniverseRenderer(universe)

    title = episode_data.get("title", "Untitled Episode")
    scenes = episode_data.get("scenes", [])

    if not scenes:
        logger.error("No scenes in episode data")
        return None

    logger.info(f"=== Generating Episode: {title} ({len(scenes)} scenes) ===")

    # 1. TTS Narration
    logger.info("Step 1: TTS Narration")
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    narrations = [
        (s.get("scene_id", i + 1), s.get("narration", ""))
        for i, s in enumerate(scenes)
        if s.get("narration", "").strip()
    ]

    narration_files = tts.generate_narrations_sync(
        narrations, audio_dir, voice=voice, rate=voice_rate
    )
    audio_durations = audio.get_all_durations(narration_files)
    total_dur = sum(audio_durations)
    logger.info(f"  {len(narration_files)} narrations, {total_dur:.0f}s ({total_dur/60:.1f}min)")

    # Update scene durations with actual narration lengths
    for i, scene in enumerate(scenes):
        if i < len(audio_durations):
            scene["duration_sec"] = audio_durations[i]

    # 2. Scene Images + Videos
    logger.info("Step 2: Scene Images & Videos")
    assets = renderer.render_episode_assets(
        scenes=scenes,
        output_dir=output_dir,
        animate=animate,
    )

    image_files = [Path(f) for f in assets["image_files"]]
    video_clips = assets["video_clips"]

    # 3. Subtitles
    logger.info("Step 3: Subtitles")
    subtitle_dir = output_dir / "subtitles"
    subtitle_dir.mkdir(exist_ok=True)
    srt_path = subtitle_dir / "subtitles.srt"
    subtitle.generate_srt(scenes, audio_durations, srt_path)

    # 4. Assembly
    logger.info("Step 4: Video Assembly")
    assembly_dir = output_dir / "assembly"
    assembly_dir.mkdir(exist_ok=True)

    min_count = min(len(narration_files), len(image_files))
    clip_paths = []

    for i in range(min_count):
        clip = assembly_dir / f"clip_{i:03d}.mp4"
        sid = scenes[i].get("scene_id", i + 1)
        duration = audio_durations[i]
        ai_video = video_clips.get(str(sid))

        if ai_video and Path(ai_video).exists():
            video.create_scene_clip_from_video(
                Path(ai_video), narration_files[i], clip,
                duration=duration, resolution=(1920, 1080),
            )
        else:
            video.create_scene_clip(
                image_files[i], narration_files[i], clip,
                duration=duration, resolution=(1920, 1080), motion=True,
            )
        clip_paths.append(clip)

    raw = assembly_dir / "raw_concat.mp4"
    video.concatenate_clips(clip_paths, raw)

    final = output_dir / "output" / f"{_safe_filename(title)}.mp4"
    final.parent.mkdir(exist_ok=True)
    video.burn_subtitles(raw, srt_path, final)

    # Copy to output path if specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, output_path)
        final = output_path

    logger.info(f"=== Episode Complete: {final} ===")
    return final


def _safe_filename(text: str) -> str:
    """Convert text to a safe filename."""
    import re
    safe = re.sub(r'[^\w\s가-힣-]', '', text)
    return safe.strip().replace(' ', '_')[:50]
