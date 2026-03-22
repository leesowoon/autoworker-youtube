"""Tests for AI image generation service."""

from pathlib import Path

from autoworker_youtube.services.image_ai import (
    IMAGE_PROVIDERS,
    generate_image,
    generate_scene_images_ai,
)


class TestImageProviders:
    def test_provider_order(self):
        assert IMAGE_PROVIDERS == ["dalle", "grok", "stability", "whisk"]

    def test_generate_image_no_keys(self, tmp_path):
        """Without API keys, all providers should fail gracefully."""
        result = generate_image(
            prompt="test image",
            output_path=tmp_path / "test.jpg",
            fallback=True,
        )
        # Should return None since no API keys are set
        assert result is None

    def test_generate_scene_images_fallback(self, tmp_path):
        """Should fall back to text cards when AI fails."""
        scenes = [
            {
                "scene_id": 1,
                "type": "hook",
                "image_prompt": "A dramatic scene",
                "text_overlay": "Hook Text",
                "narration": "Test narration",
            },
            {
                "scene_id": 2,
                "type": "feature",
                "image_prompt": "",
                "text_overlay": "Feature Text",
                "narration": "Another narration",
            },
        ]
        results = generate_scene_images_ai(scenes, tmp_path)
        assert len(results) == 2
        # All should be text card fallbacks since no API keys
        for path in results:
            assert path.exists()

    def test_generate_image_specific_provider(self, tmp_path):
        """Specifying a provider without fallback returns None if key missing."""
        result = generate_image(
            prompt="test",
            output_path=tmp_path / "test.jpg",
            provider="dalle",
            fallback=False,
        )
        assert result is None
