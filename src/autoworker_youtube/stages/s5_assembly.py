"""Stage 5: Video assembly - combine all assets into final video or CapCut project.

Supports:
  - Ken Burns motion effects on still images (default)
  - AI-generated video clips (Grok) when available
  - Static images as fallback
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.models import StageResult
from autoworker_youtube.services import video
from autoworker_youtube.stages.base import StageBase


class AssemblyStage(StageBase):
    name = "s5_assembly"

    def execute(self) -> StageResult:
        s4_data = self.load_result("s4_assets_result.json")
        s3_data = self.load_result("s3_script_result.json")
        scenes = s3_data["script"]["scenes"]

        narration_files = [Path(f) for f in s4_data["narration_files"]]
        image_files = [Path(f) for f in s4_data["image_files"]]
        subtitle_file = Path(s4_data["subtitle_file"]) if s4_data.get("subtitle_file") else None
        audio_durations = s4_data.get("audio_durations", [])
        title = s3_data["script"].get("title", "Untitled")

        # Check for AI-generated video clips
        video_clips = s4_data.get("video_clips", {})  # {scene_id: path}

        if self.config.output_format == "capcut":
            return self._assemble_capcut(
                scenes, narration_files, image_files, subtitle_file,
                audio_durations, title,
            )
        else:
            return self._assemble_mp4(
                scenes, narration_files, image_files, subtitle_file,
                audio_durations, title, video_clips,
            )

    def _assemble_mp4(
        self,
        scenes: list[dict],
        narration_files: list[Path],
        image_files: list[Path],
        subtitle_file: Path | None,
        audio_durations: list[float],
        title: str,
        video_clips: dict = None,
    ) -> StageResult:
        """Assemble into MP4 video with motion effects and AI video support."""
        video_clips = video_clips or {}
        assembly_dir = self.get_subdir("assembly")
        output_dir = self.get_subdir("output")

        min_count = min(len(narration_files), len(image_files))
        if min_count == 0:
            return StageResult(
                stage_name=self.name, success=False, error="No assets to assemble"
            )

        # Create individual scene clips
        logger.info(f"Creating {min_count} scene clips with motion effects...")
        clip_paths = []
        for i in range(min_count):
            clip_path = assembly_dir / f"clip_{i:03d}.mp4"
            duration = audio_durations[i] if i < len(audio_durations) else None
            scene = scenes[i] if i < len(scenes) else {}
            scene_id = scene.get("scene_id", i + 1)

            # Check if we have an AI video clip for this scene
            ai_video_path = video_clips.get(str(scene_id))
            if ai_video_path and Path(ai_video_path).exists():
                logger.info(f"  Scene {scene_id}: using AI video clip")
                video.create_scene_clip_from_video(
                    video_path=Path(ai_video_path),
                    audio_path=narration_files[i],
                    output_path=clip_path,
                    duration=duration,
                    resolution=self.config.resolution,
                )
            else:
                # Use image with Ken Burns motion
                video.create_scene_clip(
                    image_path=image_files[i],
                    audio_path=narration_files[i],
                    output_path=clip_path,
                    duration=duration,
                    resolution=self.config.resolution,
                    motion=True,
                )

            clip_paths.append(clip_path)

        # Concatenate all clips
        raw_video = assembly_dir / "raw_concat.mp4"
        video.concatenate_clips(clip_paths, raw_video)

        # Burn subtitles
        final_video = output_dir / "final.mp4"
        if subtitle_file and subtitle_file.exists():
            video.burn_subtitles(raw_video, subtitle_file, final_video)
        else:
            shutil.copy2(raw_video, final_video)

        # Add BGM if available
        bgm_dir = Path(self.workspace).parent.parent / "assets" / "bgm"
        bgm_files = list(bgm_dir.glob("*.mp3")) if bgm_dir.exists() else []
        if bgm_files:
            with_bgm = output_dir / "final_bgm.mp4"
            video.add_bgm(final_video, bgm_files[0], with_bgm)
            final_video = with_bgm

        # Copy to user-specified output path
        if self.config.output_path:
            output = Path(self.config.output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_video, output)
            final_video = output

        data = {
            "output_path": str(final_video),
            "output_format": "mp4",
            "clip_count": len(clip_paths),
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _assemble_capcut(
        self,
        scenes: list[dict],
        narration_files: list[Path],
        image_files: list[Path],
        subtitle_file: Path | None,
        audio_durations: list[float],
        title: str,
    ) -> StageResult:
        """Assemble into CapCut project."""
        from autoworker_youtube.services.capcut import create_capcut_project

        output_dir = self.get_subdir("output")

        project_dir = create_capcut_project(
            scenes=scenes,
            narration_files=narration_files,
            image_files=image_files,
            subtitle_file=subtitle_file,
            audio_durations=audio_durations,
            title=title,
            output_dir=output_dir,
            resolution=self.config.resolution,
        )

        data = {
            "output_path": str(project_dir),
            "output_format": "capcut",
            "clip_count": min(len(narration_files), len(image_files)),
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)
