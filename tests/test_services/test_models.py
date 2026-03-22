"""Tests for data models."""

from autoworker_youtube.core.models import (
    CommentAnalysis,
    JobConfig,
    InputMode,
    Scene,
    TitleCandidate,
    VideoScript,
    VideoType,
)


class TestJobConfig:
    def test_default_values(self):
        config = JobConfig(youtube_url="https://www.youtube.com/watch?v=test1234567")
        assert config.input_mode == InputMode.URL
        assert config.language == "ko"
        assert config.target_duration_sec == 120
        assert config.video_type == VideoType.PRODUCT_INTRO
        assert config.job_id  # auto-generated
        assert config.include_comments is True
        assert config.title_candidates == 3
        assert config.auto_select_title is True
        assert config.output_format == "mp4"

    def test_multi_url_mode(self):
        config = JobConfig(
            input_mode=InputMode.MULTI_URL,
            youtube_urls=[
                "https://www.youtube.com/watch?v=aaa11111111",
                "https://www.youtube.com/watch?v=bbb22222222",
            ],
        )
        assert config.input_mode == InputMode.MULTI_URL
        assert len(config.youtube_urls) == 2

    def test_trending_mode(self):
        config = JobConfig(input_mode=InputMode.TRENDING, topic="AI")
        assert config.input_mode == InputMode.TRENDING
        assert config.topic == "AI"
        assert config.youtube_url is None

    def test_capcut_output(self):
        config = JobConfig(
            youtube_url="https://www.youtube.com/watch?v=test1234567",
            output_format="capcut",
        )
        assert config.output_format == "capcut"


class TestVideoScript:
    def test_script_with_title_candidates(self):
        script = VideoScript(
            title="Best Title",
            title_candidates=[
                TitleCandidate(title="Title A", style="흥미유발", score=8.5),
                TitleCandidate(title="Title B", style="정보전달", score=7.0),
                TitleCandidate(title="Best Title", style="감성", score=9.0),
            ],
            total_duration_sec=60,
            scenes=[
                Scene(
                    scene_id=1,
                    type="hook",
                    duration_sec=10,
                    narration="Hello world",
                    image_prompt="A dramatic opening scene",
                )
            ],
        )
        assert len(script.title_candidates) == 3
        assert script.title == "Best Title"
        assert script.scenes[0].image_prompt == "A dramatic opening scene"

    def test_comment_analysis(self):
        ca = CommentAnalysis(
            total_comments=50,
            top_sentiments=["편안함", "호기심"],
            key_opinions=["더 길었으면 좋겠다"],
            emotional_tone="긍정적",
        )
        assert ca.total_comments == 50
        assert "편안함" in ca.top_sentiments
