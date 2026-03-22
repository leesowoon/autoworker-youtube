"""Stage 3: Script generation with multiple title candidates."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.models import AnalysisReport, InputMode, StageResult
from autoworker_youtube.stages.base import StageBase

MANUAL_PAUSE = "MANUAL_LLM_PAUSE"


class ScriptStage(StageBase):
    name = "s3_script"

    def execute(self) -> StageResult:
        # Manual mode: check if result already exists
        result_path = self.workspace / "s3_script_result.json"
        if self.config.llm_mode == "manual":
            if result_path.exists():
                logger.info("Manual mode: loading existing s3_script_result.json")
                data = self.load_result("s3_script_result.json")
                return StageResult(stage_name=self.name, success=True, data=data)
            else:
                self._save_prompt_data()
                return StageResult(
                    stage_name=self.name,
                    success=False,
                    error=f"{MANUAL_PAUSE}: s3_script_result.json 파일이 필요합니다. "
                          f"Claude Code에서 workspace/{self.config.job_id}/s3_prompt.json을 "
                          f"참고하여 s3_script_result.json을 생성해주세요.",
                )

        # API mode
        s2_data = self.load_result("s2_analysis_result.json")

        if s2_data.get("trending_data") or self.config.input_mode == InputMode.TRENDING:
            return self._generate_trending_script(s2_data)
        else:
            return self._generate_script(s2_data)

    def _save_prompt_data(self):
        """Save formatted data for Claude Code to process."""
        import json

        s2_data = self.load_result("s2_analysis_result.json")

        prompt_data = {
            "stage": "s3_script",
            "instruction": (
                f"아래 분석 결과를 기반으로 {self.config.target_duration_sec}초 길이의 "
                f"'{self.config.video_type.value}' 영상 스크립트를 생성하여 "
                f"s3_script_result.json을 만들어주세요."
            ),
            "analysis": s2_data.get("analysis", {}),
            "video_type": self.config.video_type.value,
            "target_duration_sec": self.config.target_duration_sec,
            "title_candidates_count": self.config.title_candidates,
            "output_schema": {
                "script": {
                    "title": "최종 선택된 제목",
                    "title_candidates": [
                        {"title": "후보", "style": "스타일", "reason": "이유", "score": 8.5}
                    ],
                    "concept": "영상 컨셉",
                    "target_viewer": "타겟 시청자",
                    "total_duration_sec": self.config.target_duration_sec,
                    "scenes": [
                        {
                            "scene_id": 1,
                            "type": "hook",
                            "duration_sec": 8,
                            "narration": "나레이션 텍스트",
                            "visual_direction": "시각 연출",
                            "text_overlay": "화면 텍스트 or null",
                            "transition": "fade",
                            "image_prompt": "영문 이미지 생성 프롬프트",
                        }
                    ],
                }
            },
        }

        prompt_path = self.workspace / "s3_prompt.json"
        with open(prompt_path, "w", encoding="utf-8") as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved prompt data: {prompt_path}")

    def _generate_script(self, s2_data: dict) -> StageResult:
        """Generate script from analysis (single or multi-URL)."""
        from autoworker_youtube.services import llm

        analysis = AnalysisReport(**s2_data["analysis"])

        script = llm.generate_script(
            analysis=analysis,
            video_type=self.config.video_type.value,
            target_duration=self.config.target_duration_sec,
            language=self.config.language,
            num_title_candidates=self.config.title_candidates,
            auto_select=self.config.auto_select_title,
        )

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
        from autoworker_youtube.services import llm

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

        self.save_result(
            {"analysis": analysis.model_dump()},
            filename="s2_analysis_result.json",
        )

        if script.title_candidates:
            logger.info("제목 후보:")
            for i, tc in enumerate(script.title_candidates, 1):
                marker = " ★" if tc.title == script.title else ""
                logger.info(f"  {i}. [{tc.score}점] {tc.title} ({tc.style}){marker}")

        data = {"script": script.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)
