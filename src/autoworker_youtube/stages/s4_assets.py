"""Stage 4: Asset generation (TTS, images, subtitles)."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.models import StageResult, VideoScript
from autoworker_youtube.services import audio, image, subtitle, tts
from autoworker_youtube.stages.base import StageBase


class AssetStage(StageBase):
    name = "s4_assets"

    def execute(self) -> StageResult:
        s3_data = self.load_result("s3_script_result.json")
        script = VideoScript(**s3_data["script"])

        # Prepare directories
        audio_dir = self.get_subdir("audio")
        image_dir = self.get_subdir("images")
        subtitle_dir = self.get_subdir("subtitles")

        # 1. Generate TTS narrations
        narrations = [
            (scene.scene_id, scene.narration)
            for scene in script.scenes
            if scene.narration.strip()
        ]

        narration_files = tts.generate_narrations_sync(
            narrations=narrations,
            output_dir=audio_dir,
            voice=self.config.voice_id,
        )

        # 2. Get actual audio durations
        audio_durations = audio.get_all_durations(narration_files)

        # 3. Generate scene images (AI or text card fallback)
        scene_dicts = [s.model_dump() for s in script.scenes]
        image_files = self._generate_images(scene_dicts, image_dir)

        # 4. Generate subtitles
        srt_path = subtitle_dir / "subtitles.srt"
        subtitle.generate_srt(
            scenes=scene_dicts,
            audio_durations=audio_durations,
            output_path=srt_path,
        )

        # Save asset manifest
        data = {
            "narration_files": [str(f) for f in narration_files],
            "audio_durations": audio_durations,
            "image_files": [str(f) for f in image_files],
            "subtitle_file": str(srt_path),
            "scene_count": len(script.scenes),
        }
        self.save_result(data)

        return StageResult(stage_name=self.name, success=True, data=data)

    def _generate_images(self, scenes: list[dict], image_dir) -> list:
        """Generate images - try AI providers first, fallback to text cards."""
        image_provider = getattr(self.config, "image_provider", None)

        # Check if any scene has an image_prompt and AI providers are configured
        has_prompts = any(s.get("image_prompt") for s in scenes)
        if has_prompts and image_provider != "none":
            try:
                from autoworker_youtube.services.image_ai import generate_scene_images_ai

                logger.info(f"Attempting AI image generation (provider={image_provider or 'auto'})...")
                return generate_scene_images_ai(
                    scenes=scenes,
                    output_dir=image_dir,
                    provider=image_provider,
                    fallback=True,
                )
            except Exception as e:
                logger.warning(f"AI image generation failed, using text cards: {e}")

        # Fallback: text cards
        return image.create_scene_images(
            scenes=scenes,
            output_dir=image_dir,
            resolution=self.config.resolution,
        )
