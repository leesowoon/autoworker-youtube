"""Tests for AI image generation service."""

from autoworker_youtube.services.image_ai import (
    IMAGE_PROVIDERS,
)


class TestImageProviders:
    def test_provider_order(self):
        assert IMAGE_PROVIDERS == ["gpt_image", "grok", "stability", "whisk"]

    def test_generate_scene_images_no_prompt(self, tmp_path):
        """Scenes without image_prompt should get text card fallbacks."""
        from autoworker_youtube.services.image_ai import generate_scene_images_ai

        scenes = [
            {
                "scene_id": 1,
                "type": "hook",
                "image_prompt": "",
                "text_overlay": "Fallback Text",
                "narration": "Test narration",
            },
        ]
        results = generate_scene_images_ai(scenes, tmp_path)
        assert len(results) == 1
        assert results[0].exists()
