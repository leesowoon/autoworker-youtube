"""Universe-aware image and video renderer.

Generates scene images/videos using character sheets as references
to maintain visual consistency across episodes.
"""

from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings as app_settings
from autoworker_youtube.universe.world import BoriUniverse


class UniverseRenderer:
    """Renders scenes with consistent characters from the Bori Universe."""

    def __init__(self, universe: BoriUniverse | None = None):
        self.universe = universe or BoriUniverse()

    def render_scene_image(
        self,
        scene_description: str,
        char_ids: list[str],
        location_id: str | None = None,
        output_path: Path | None = None,
        extra_direction: str = "",
    ) -> Path | None:
        """Generate a scene image with consistent characters.

        Uses character sheets as references via images.edit() API.

        Args:
            scene_description: What's happening in the scene.
            char_ids: Character IDs appearing in this scene.
            location_id: Location ID for the background.
            output_path: Where to save the image.
            extra_direction: Additional visual direction.

        Returns:
            Path to generated image or None.
        """
        if not app_settings.openai_api_key:
            logger.warning("OPENAI_API_KEY not set")
            return None

        # Build prompt
        prompt = self.universe.build_scene_prompt(
            scene_description, char_ids, location_id, extra_direction
        )

        # Get character reference sheets
        ref_sheets = self.universe.get_reference_sheets(char_ids)

        if not output_path:
            output_path = Path(f"scene_{'-'.join(char_ids)}.png")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            from openai import OpenAI

            client = OpenAI(api_key=app_settings.openai_api_key)

            if ref_sheets:
                # Use images.edit with character references
                ref_files = [open(r, "rb") for r in ref_sheets[:10]]  # max 10 refs
                result = client.images.edit(
                    model="gpt-image-1",
                    image=ref_files,
                    prompt=prompt,
                    size="1536x1024",
                    quality="high",
                )
                for f in ref_files:
                    f.close()
            else:
                # No references, use generate
                result = client.images.generate(
                    model="gpt-image-1.5",
                    prompt=prompt,
                    size="1536x1024",
                    quality="high",
                    n=1,
                )

            img_data = result.data[0].b64_json
            if img_data:
                output_path.write_bytes(base64.b64decode(img_data))
                logger.info(f"Scene image saved: {output_path}")
                return output_path

            return None
        except Exception as e:
            logger.error(f"Scene image generation failed: {e}")
            return None

    def render_scene_video(
        self,
        image_path: Path,
        animation_prompt: str,
        output_path: Path,
        duration: int = 10,
    ) -> Path | None:
        """Animate a scene image using Grok Image-to-Video.

        Args:
            image_path: Source scene image.
            animation_prompt: How to animate the scene.
            output_path: Where to save the video.
            duration: Video duration (max 15s).
        """
        if not app_settings.xai_api_key:
            logger.warning("XAI_API_KEY not set")
            return None

        try:
            from autoworker_youtube.services.image_ai import generate_grok_image_to_video

            return generate_grok_image_to_video(
                image_path=image_path,
                prompt=animation_prompt,
                output_path=output_path,
                duration=min(duration, 15),
            )
        except Exception as e:
            logger.error(f"Scene video generation failed: {e}")
            return None

    def render_episode_assets(
        self,
        scenes: list[dict],
        output_dir: Path,
        animate: bool = True,
    ) -> dict:
        """Render all images and videos for an episode.

        Args:
            scenes: List of scene dicts with keys:
                - scene_id, narration, char_ids, location_id,
                  visual_direction, animation_prompt, duration_sec
            output_dir: Directory to save all assets.
            animate: Whether to generate animated videos.

        Returns:
            Dict with image_files and video_clips paths.
        """
        images_dir = output_dir / "images"
        videos_dir = output_dir / "videos"
        images_dir.mkdir(parents=True, exist_ok=True)
        videos_dir.mkdir(parents=True, exist_ok=True)

        image_files = []
        video_clips = {}

        for scene in scenes:
            sid = scene.get("scene_id", 0)
            char_ids = scene.get("char_ids", ["bori"])
            location_id = scene.get("location_id")
            description = scene.get("visual_direction", scene.get("narration", ""))
            anim_prompt = scene.get("animation_prompt", "Gentle natural motion, subtle movements")
            duration = scene.get("duration_sec", 10)

            # 1. Generate image
            img_path = images_dir / f"scene_{sid:03d}.png"
            logger.info(f"Rendering scene {sid} image...")
            result = self.render_scene_image(
                scene_description=description,
                char_ids=char_ids,
                location_id=location_id,
                output_path=img_path,
            )

            if result:
                image_files.append(result)
            else:
                # Fallback text card
                from autoworker_youtube.services.image import create_text_card

                fallback = images_dir / f"scene_{sid:03d}.jpg"
                create_text_card(
                    text=scene.get("narration", "")[:50],
                    output_path=fallback,
                    subtitle=scene.get("type", "scene").upper(),
                )
                image_files.append(fallback)

            # 2. Generate video (if animate=True)
            if animate and result:
                vid_path = videos_dir / f"scene_{sid:03d}.mp4"
                vid_duration = min(int(duration), 15)
                logger.info(f"Rendering scene {sid} video ({vid_duration}s)...")
                vid_result = self.render_scene_video(
                    image_path=result,
                    animation_prompt=anim_prompt,
                    output_path=vid_path,
                    duration=vid_duration,
                )
                if vid_result:
                    video_clips[str(sid)] = str(vid_result)

        logger.info(
            f"Episode assets: {len(image_files)} images, "
            f"{len(video_clips)} videos"
        )

        return {
            "image_files": [str(f) for f in image_files],
            "video_clips": video_clips,
        }
