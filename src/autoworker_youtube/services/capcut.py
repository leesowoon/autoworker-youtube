"""CapCut project file generator.

Generates a CapCut-compatible project structure (draft_content.json)
that can be imported into CapCut for further editing.

CapCut stores projects in:
  ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from loguru import logger


def _generate_id() -> str:
    """Generate a unique ID for CapCut elements."""
    return uuid.uuid4().hex[:24].upper()


def _seconds_to_microseconds(seconds: float) -> int:
    """Convert seconds to microseconds (CapCut's time unit)."""
    return int(seconds * 1_000_000)


def create_capcut_project(
    scenes: list[dict],
    narration_files: list[Path],
    image_files: list[Path],
    subtitle_file: Path | None,
    audio_durations: list[float],
    title: str,
    output_dir: Path,
    resolution: tuple[int, int] = (1920, 1080),
) -> Path:
    """Create a CapCut-compatible project directory.

    Args:
        scenes: Scene definitions from the script.
        narration_files: Paths to narration audio files.
        image_files: Paths to scene background images.
        subtitle_file: Path to SRT subtitle file.
        audio_durations: Duration of each narration in seconds.
        title: Project title.
        output_dir: Directory to create the project in.
        resolution: Video resolution.

    Returns:
        Path to the created project directory.
    """
    project_id = _generate_id()
    project_dir = output_dir / f"capcut_{project_id}"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create materials directory and copy files
    materials_dir = project_dir / "materials"
    materials_dir.mkdir(exist_ok=True)

    # Copy narration files
    copied_narrations = []
    for f in narration_files:
        if f.exists():
            dest = materials_dir / f.name
            shutil.copy2(f, dest)
            copied_narrations.append(dest)

    # Copy image files
    copied_images = []
    for f in image_files:
        if f.exists():
            dest = materials_dir / f.name
            shutil.copy2(f, dest)
            copied_images.append(dest)

    # Build draft_content.json
    draft = _build_draft_content(
        scenes=scenes,
        narration_files=copied_narrations,
        image_files=copied_images,
        audio_durations=audio_durations,
        title=title,
        project_id=project_id,
        resolution=resolution,
    )

    # Write draft_content.json
    draft_path = project_dir / "draft_content.json"
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)

    # Write draft_meta_info.json
    meta = {
        "draft_id": project_id,
        "draft_name": title,
        "draft_resolution": f"{resolution[0]}x{resolution[1]}",
        "draft_removable_storage_device": "",
    }
    meta_path = project_dir / "draft_meta_info.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Create import instructions
    readme_path = project_dir / "IMPORT_GUIDE.txt"
    readme_path.write_text(
        f"""CapCut 프로젝트 가져오기 가이드
================================

프로젝트명: {title}
생성일시: auto-generated

방법 1: 직접 가져오기
1. 이 폴더 전체를 아래 경로에 복사하세요:
   - Mac: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/
   - Windows: C:\\Users\\<사용자>\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft\\
2. CapCut을 재시작하면 프로젝트 목록에 나타납니다.

방법 2: 수동 편집
1. CapCut에서 새 프로젝트를 생성하세요.
2. materials/ 폴더의 파일들을 타임라인에 순서대로 배치하세요.
   - 이미지: 비디오 트랙
   - 나레이션: 오디오 트랙
3. 각 클립의 길이를 아래 정보에 맞춰 조정하세요:

클립 정보:
""",
        encoding="utf-8",
    )

    # Append clip info
    with open(readme_path, "a", encoding="utf-8") as f:
        current_time = 0.0
        for i, (scene, duration) in enumerate(zip(scenes, audio_durations)):
            f.write(
                f"  Scene {i+1} [{scene.get('type', 'scene')}]: "
                f"{current_time:.1f}s ~ {current_time + duration:.1f}s "
                f"({duration:.1f}초)\n"
            )
            if i < len(copied_images):
                f.write(f"    이미지: {copied_images[i].name}\n")
            if i < len(copied_narrations):
                f.write(f"    나레이션: {copied_narrations[i].name}\n")
            narration = scene.get("narration", "")
            if narration:
                f.write(f"    대사: {narration[:80]}...\n")
            f.write("\n")
            current_time += duration

    logger.info(f"CapCut project created: {project_dir}")
    return project_dir


def _build_draft_content(
    scenes: list[dict],
    narration_files: list[Path],
    image_files: list[Path],
    audio_durations: list[float],
    title: str,
    project_id: str,
    resolution: tuple[int, int],
) -> dict:
    """Build the draft_content.json structure."""
    canvas_config = {
        "height": resolution[1],
        "ratio": "original",
        "width": resolution[0],
    }

    # Build video tracks
    video_segments = []
    audio_segments = []
    text_segments = []
    current_time_us = 0

    min_count = min(len(image_files), len(narration_files), len(audio_durations))

    for i in range(min_count):
        duration_us = _seconds_to_microseconds(audio_durations[i])
        segment_id = _generate_id()

        # Video segment (image)
        video_segments.append({
            "id": segment_id,
            "material_id": f"image_{i}",
            "source_timerange": {"duration": duration_us, "start": 0},
            "target_timerange": {"duration": duration_us, "start": current_time_us},
            "type": "video",
            "extra_material_refs": [],
        })

        # Audio segment (narration)
        audio_segments.append({
            "id": _generate_id(),
            "material_id": f"audio_{i}",
            "source_timerange": {"duration": duration_us, "start": 0},
            "target_timerange": {"duration": duration_us, "start": current_time_us},
            "type": "audio",
        })

        # Text overlay (if exists)
        scene = scenes[i] if i < len(scenes) else {}
        text_overlay = scene.get("text_overlay")
        if text_overlay:
            text_segments.append({
                "id": _generate_id(),
                "material_id": f"text_{i}",
                "target_timerange": {"duration": duration_us, "start": current_time_us},
                "type": "text",
                "content": text_overlay,
            })

        current_time_us += duration_us

    # Build materials list
    materials = {"videos": [], "audios": [], "texts": []}

    for i, img in enumerate(image_files[:min_count]):
        materials["videos"].append({
            "id": f"image_{i}",
            "path": str(img.resolve()),
            "type": "photo",
            "duration": _seconds_to_microseconds(audio_durations[i]),
        })

    for i, nar in enumerate(narration_files[:min_count]):
        materials["audios"].append({
            "id": f"audio_{i}",
            "path": str(nar.resolve()),
            "type": "audio",
            "duration": _seconds_to_microseconds(audio_durations[i]),
        })

    # Build tracks
    tracks = [
        {"id": _generate_id(), "type": "video", "segments": video_segments},
        {"id": _generate_id(), "type": "audio", "segments": audio_segments},
    ]
    if text_segments:
        tracks.append(
            {"id": _generate_id(), "type": "text", "segments": text_segments}
        )

    return {
        "id": project_id,
        "name": title,
        "canvas_config": canvas_config,
        "duration": current_time_us,
        "materials": materials,
        "tracks": tracks,
        "version": "3.0.0",
        "platform": {"os": "linux", "app": "autoworker-youtube"},
    }
