"""Text-to-Speech service using edge-tts."""

from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import TTSError


async def _generate_single(text: str, output_path: Path, voice: str, rate: str) -> Path:
    """Generate TTS for a single text segment."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output_path))
    return output_path


async def generate_narrations(
    narrations: list[tuple[int, str]],
    output_dir: Path,
    voice: str | None = None,
    rate: str | None = None,
) -> list[Path]:
    """Generate TTS audio files for all narration segments.

    Args:
        narrations: List of (scene_id, narration_text) tuples.
        output_dir: Directory to save audio files.
        voice: TTS voice ID (default from settings).
        rate: Speech rate adjustment (default from settings).

    Returns:
        List of paths to generated audio files.
    """
    voice = voice or settings.tts_voice
    rate = rate or settings.tts_rate
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating {len(narrations)} narration segments with {voice}...")

    tasks = []
    paths = []
    for scene_id, text in narrations:
        path = output_dir / f"narration_{scene_id:03d}.mp3"
        paths.append(path)
        tasks.append(_generate_single(text, path, voice, rate))

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        raise TTSError(f"TTS generation failed: {e}")

    logger.info(f"Generated {len(paths)} narration files")
    return paths


def generate_narrations_sync(
    narrations: list[tuple[int, str]],
    output_dir: Path,
    voice: str | None = None,
    rate: str | None = None,
) -> list[Path]:
    """Synchronous wrapper for generate_narrations."""
    return asyncio.run(generate_narrations(narrations, output_dir, voice, rate))
