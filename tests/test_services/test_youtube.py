"""Tests for YouTube service."""

import pytest

from autoworker_youtube.services.youtube import extract_video_id
from autoworker_youtube.core.exceptions import InputError


class TestExtractVideoId:
    def test_standard_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=Lcxg0tHiT-k") == "Lcxg0tHiT-k"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/Lcxg0tHiT-k") == "Lcxg0tHiT-k"

    def test_embed_url(self):
        assert extract_video_id("https://www.youtube.com/embed/Lcxg0tHiT-k") == "Lcxg0tHiT-k"

    def test_url_with_params(self):
        assert extract_video_id("https://www.youtube.com/watch?v=QCxGe_VRi1A&t=704s") == "QCxGe_VRi1A"

    def test_shorts_url(self):
        assert extract_video_id("https://www.youtube.com/shorts/abc12345678") == "abc12345678"

    def test_invalid_url(self):
        with pytest.raises(InputError):
            extract_video_id("https://google.com")
