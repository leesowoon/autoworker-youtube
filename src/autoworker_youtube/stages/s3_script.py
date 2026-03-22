"""Stage 3: Script generation with multiple title candidates."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.models import AnalysisReport, InputMode, StageResult
from autoworker_youtube.services import llm
from autoworker_youtube.stages.base import StageBase


class ScriptStage(StageBase):
    name = "s3_script"

    def execute(self) -> StageResult:
        s2_data = self.load_result("s2_analysis_result.json")

        if s2_data.get("trending_data") or self.config.input_mode == InputMode.TRENDING:
            return self._generate_trending_script(s2_data)
        else:
            return self._generate_script(s2_data)

    def _generate_script(self, s2_data: dict) -> StageResult:
        """Generate script from analysis (single or multi-URL)."""
        analysis = AnalysisReport(**s2_data["analysis"])

        script = llm.generate_script(
            analysis=analysis,
            video_type=self.config.video_type.value,
            target_duration=self.config.target_duration_sec,
            language=self.config.language,
            num_title_candidates=self.config.title_candidates,
            auto_select=self.config.auto_select_title,
        )

        # Log title candidates
        if script.title_candidates:
            logger.info("제목 후보:")
            for i, tc in enumerate(script.title_candidates, 1):
                marker = " ★" if tc.title == script.title else ""
                logger.info(f"  {i}. [{tc.score}점] {tc.title} ({tc.style}){marker}")

        data = {"script": script.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _generate_trending_script(self, s2_data: dict) -> StageResult:
        """Generate script from trending topic research."""
        trending_data = s2_data.get("trending_data", {})
        topic_title = trending_data.get("topic_title", "")
        research_text = trending_data.get("research_text", "")

        analysis, script = llm.generate_trending_script(
            topic=topic_title,
            research_text=research_text,
            video_type=self.config.video_type.value,
            target_duration=self.config.target_duration_sec,
            language=self.config.language,
        )

        # Update analysis
        self.save_result(
            {"analysis": analysis.model_dump()},
            filename="s2_analysis_result.json",
        )

        # Log title candidates
        if script.title_candidates:
            logger.info("제목 후보:")
            for i, tc in enumerate(script.title_candidates, 1):
                marker = " ★" if tc.title == script.title else ""
                logger.info(f"  {i}. [{tc.score}점] {tc.title} ({tc.style}){marker}")

        data = {"script": script.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)
