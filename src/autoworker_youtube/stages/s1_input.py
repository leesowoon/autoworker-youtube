"""Stage 1: Input processing - fetch YouTube data or trending research."""

from __future__ import annotations

from autoworker_youtube.core.models import InputMode, JobConfig, StageResult
from autoworker_youtube.services import youtube
from autoworker_youtube.stages.base import StageBase


class InputStage(StageBase):
    name = "s1_input"

    def execute(self) -> StageResult:
        if self.config.input_mode == InputMode.MULTI_URL:
            return self._process_multi_url()
        elif self.config.input_mode == InputMode.URL:
            return self._process_url()
        else:
            return self._process_trending()

    def _process_url(self) -> StageResult:
        """Process a single YouTube URL (still fetches comments)."""
        if not self.config.youtube_url:
            return StageResult(
                stage_name=self.name, success=False, error="No YouTube URL provided"
            )

        video_id = youtube.extract_video_id(self.config.youtube_url)
        metadata = youtube.fetch_metadata(video_id)

        # Fetch transcript
        try:
            transcript = youtube.fetch_transcript(video_id, self.config.language)
            transcript_text = " ".join(seg.text for seg in transcript)
        except Exception as e:
            transcript_text = f"(자막 추출 실패: {e})"
            transcript = []

        # Fetch comments
        comments = []
        if self.config.include_comments:
            comments = youtube.fetch_comments(video_id, self.config.max_comments)

        # Download thumbnail
        raw_dir = self.get_subdir("raw")
        youtube.download_thumbnail(video_id, raw_dir)

        data = {
            "input_mode": "url",
            "video_id": video_id,
            "metadata": metadata.model_dump(),
            "transcript_text": transcript_text,
            "transcript_segments": [s.model_dump() for s in transcript],
            "comments": comments,
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _process_multi_url(self) -> StageResult:
        """Process multiple YouTube URLs with comments."""
        urls = self.config.youtube_urls
        if not urls:
            return StageResult(
                stage_name=self.name, success=False, error="No YouTube URLs provided"
            )

        references = youtube.fetch_multi_video_data(
            urls=urls,
            language=self.config.language,
            include_comments=self.config.include_comments,
            max_comments=self.config.max_comments,
        )

        # Download thumbnails
        raw_dir = self.get_subdir("raw")
        for ref in references:
            vid = ref.get("video_id", "")
            if vid:
                youtube.download_thumbnail(vid, raw_dir)

        data = {
            "input_mode": "multi_url",
            "references": references,
            "reference_count": len(references),
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _process_trending(self) -> StageResult:
        """Discover and research a trending topic."""
        from autoworker_youtube.planner.topic_selector import (
            compile_research,
            discover_topics,
        )

        topics = discover_topics(
            region=self.config.region,
            category=self.config.category,
            topic=self.config.topic,
        )

        if not topics:
            return StageResult(
                stage_name=self.name,
                success=False,
                error="No trending topics found",
            )

        selected = topics[0]
        topic_title = selected.get("title", selected.get("suggested_title", ""))
        research_text = compile_research(topic_title, self.config.region)

        # Search for related YouTube videos
        related_videos = youtube.search_videos(topic_title, max_results=3)

        data = {
            "input_mode": "trending",
            "selected_topic": selected,
            "topic_title": topic_title,
            "research_text": research_text,
            "all_topics": topics,
            "related_videos": [v.model_dump() for v in related_videos],
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)
