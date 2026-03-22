"""Stage 4: Asset generation (TTS, images, AI video from images, subtitles)."""

from __future__ import annotations

from pathlib import Path

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
        video_dir = self.get_subdir("videos")
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

        # 4. Convert images to animated video clips (Image-to-Video)
        video_clips = self._image_to_video(
            scene_dicts, image_files, video_dir, audio_durations
        )

        # 5. Generate subtitles
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
            "video_clips": video_clips,
            "subtitle_file": str(srt_path),
            "scene_count": len(script.scenes),
        }
        self.save_result(data)

        return StageResult(stage_name=self.name, success=True, data=data)

    def _generate_images(self, scenes: list[dict], image_dir) -> list:
        """Generate images - try AI providers first, fallback to text cards."""
        image_provider = getattr(self.config, "image_provider", None)

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

        return image.create_scene_images(
            scenes=scenes,
            output_dir=image_dir,
            resolution=self.config.resolution,
        )

    def _image_to_video(
        self,
        scenes: list[dict],
        image_files: list,
        video_dir: Path,
        audio_durations: list[float],
    ) -> dict:
        """Convert generated images to animated videos using Grok Image-to-Video.

        Returns dict of {scene_id: video_path} for successful conversions.
        """
        from autoworker_youtube.core.config import settings as app_settings

        if not app_settings.xai_api_key:
            logger.info("XAI_API_KEY not set, skipping image-to-video")
            return {}

        try:
            from autoworker_youtube.services.image_ai import generate_grok_image_to_video
        except ImportError:
            return {}

        video_clips = {}

        for i, scene in enumerate(scenes):
            if i >= len(image_files):
                break

            scene_id = scene.get("scene_id", i + 1)
            scene_type = scene.get("type", "")
            image_path = Path(image_files[i])

            if not image_path.exists():
                continue

            # Build animation prompt based on scene type
            narration = scene.get("narration", "")
            visual = scene.get("visual_direction", "")
            anim_prompt = self._build_animation_prompt(scene_type, narration, visual)

            # Match video duration to narration length (Grok max 15s)
            narration_dur = audio_durations[i] if i < len(audio_durations) else 5
            duration = min(int(narration_dur), 15)
            video_path = video_dir / f"scene_video_{scene_id:03d}.mp4"

            logger.info(f"Image-to-Video scene {scene_id} [{scene_type}]: {anim_prompt[:60]}...")
            result = generate_grok_image_to_video(
                image_path=image_path,
                prompt=anim_prompt,
                output_path=video_path,
                duration=duration,
            )

            if result and result.exists():
                video_clips[str(scene_id)] = str(result)
                logger.info(f"  Scene {scene_id}: animated video OK")
            else:
                logger.info(f"  Scene {scene_id}: will use image + Ken Burns")

        logger.info(f"Image-to-Video: {len(video_clips)}/{len(scenes)} scenes animated")
        return video_clips

    def _build_animation_prompt(self, scene_type: str, narration: str, visual: str) -> str:
        """Build a natural animation prompt for image-to-video."""
        prompts = {
            "hook": "Dramatic slow motion, the person moves naturally, subtle lighting changes, cinematic atmosphere, tension building",
            "problem": "Slow worried movements, person looking stressed, papers shuffling, urgent feeling, dramatic lighting shifts",
            "introduction": "Confident reveal, shield glowing brighter, elements floating into place, hopeful energy, smooth camera push in",
            "feature": "Smooth demonstration motion, UI elements appearing, data flowing through the system, clean professional movement",
            "closing": "Person standing confidently, subtle breathing motion, gentle camera pull back, inspirational ending feel",
        }

        base = prompts.get(scene_type, "Gentle natural motion, subtle movements, cinematic feel")

        if visual:
            base = f"{visual}. {base}"

        return base
