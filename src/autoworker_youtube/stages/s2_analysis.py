"""Stage 2: Content analysis using LLM (with comment analysis)."""

from __future__ import annotations

from autoworker_youtube.core.models import InputMode, StageResult
from autoworker_youtube.services import llm
from autoworker_youtube.stages.base import StageBase


class AnalysisStage(StageBase):
    name = "s2_analysis"

    def execute(self) -> StageResult:
        s1_data = self.load_result("s1_input_result.json")
        input_mode = s1_data.get("input_mode", self.config.input_mode.value)

        if input_mode == "multi_url":
            return self._analyze_multi(s1_data)
        elif input_mode == "trending":
            return self._analyze_trending(s1_data)
        else:
            return self._analyze_youtube(s1_data)

    def _analyze_youtube(self, s1_data: dict) -> StageResult:
        """Analyze single YouTube video with comments."""
        metadata = s1_data["metadata"]
        transcript_text = s1_data.get("transcript_text", "")
        comments = s1_data.get("comments", [])

        metadata_summary = (
            f"제목: {metadata['title']}\n"
            f"채널: {metadata['channel']}\n"
            f"설명: {metadata['description'][:500]}\n"
            f"태그: {', '.join(metadata.get('tags', [])[:10])}\n"
            f"조회수: {metadata.get('view_count', 0):,}\n"
            f"구독자: {metadata.get('subscriber_count', 0):,}\n"
            f"길이: {metadata.get('duration_sec', 0)}초"
        )

        # Format comments
        comments_text = ""
        if comments:
            comments_text = "\n".join(
                f"[{c.get('likes', 0)}좋아요] {c.get('text', '')}"
                for c in comments[:20]
            )

        analysis = llm.analyze_content(
            transcript_text=transcript_text,
            metadata_summary=metadata_summary,
            comments_text=comments_text,
            language=self.config.language,
        )

        data = {"analysis": analysis.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _analyze_multi(self, s1_data: dict) -> StageResult:
        """Analyze multiple reference videos together."""
        references = s1_data.get("references", [])

        if not references:
            return StageResult(
                stage_name=self.name,
                success=False,
                error="No reference data found",
            )

        analysis = llm.analyze_multi_references(
            references=references,
            language=self.config.language,
        )

        data = {"analysis": analysis.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _analyze_trending(self, s1_data: dict) -> StageResult:
        """Pass through trending data to Stage 3 for combined analysis+script."""
        data = {
            "analysis": {
                "summary": f"트렌딩 주제: {s1_data.get('topic_title', '')}",
                "key_topics": [s1_data.get("topic_title", "")],
                "product_features": [],
                "target_audience": "일반 대중",
                "tone": "정보 전달",
                "segments": [],
                "source_type": "trending",
            },
            "trending_data": s1_data,
        }
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)
