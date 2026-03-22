"""Subtitle generation service."""

from __future__ import annotations

from pathlib import Path

from loguru import logger


def _format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(
    scenes: list[dict],
    audio_durations: list[float],
    output_path: Path,
) -> Path:
    """Generate SRT subtitle file from scenes and audio durations.

    Args:
        scenes: List of scene dicts with narration text.
        audio_durations: Actual duration of each narration audio in seconds.
        output_path: Path to save the SRT file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current_time = 0.0
    srt_entries = []

    for i, (scene, duration) in enumerate(zip(scenes, audio_durations), 1):
        narration = scene.get("narration", "").strip()
        if not narration:
            current_time += duration
            continue

        start_time = current_time
        end_time = current_time + duration

        # Split long narrations into chunks for readability
        sentences = _split_narration(narration)
        chunk_duration = duration / max(len(sentences), 1)

        for j, sentence in enumerate(sentences):
            chunk_start = start_time + j * chunk_duration
            chunk_end = chunk_start + chunk_duration

            srt_entries.append(
                f"{len(srt_entries) + 1}\n"
                f"{_format_srt_time(chunk_start)} --> {_format_srt_time(chunk_end)}\n"
                f"{sentence}\n"
            )

        current_time = end_time

    srt_content = "\n".join(srt_entries)
    output_path.write_text(srt_content, encoding="utf-8")
    logger.info(f"Generated SRT subtitle: {output_path}")
    return output_path


def _split_narration(text: str, max_chars: int = 40) -> list[str]:
    """Split narration into subtitle-sized chunks."""
    # Split by sentence endings
    import re

    sentences = re.split(r"(?<=[.?!。])\s*", text)
    chunks = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            # Split long sentences by commas or spaces
            words = sentence.split(", ")
            current = ""
            for word in words:
                if len(current) + len(word) + 2 > max_chars and current:
                    chunks.append(current)
                    current = word
                else:
                    current = f"{current}, {word}" if current else word
            if current:
                chunks.append(current)

    return chunks if chunks else [text]
