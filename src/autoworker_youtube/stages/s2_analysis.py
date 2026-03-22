"""Stage 2: Content analysis using LLM (with comment analysis)."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from autoworker_youtube.core.models import InputMode, StageResult
from autoworker_youtube.stages.base import StageBase

# Sentinel error prefix for manual LLM pause
MANUAL_PAUSE = "MANUAL_LLM_PAUSE"


class AnalysisStage(StageBase):
    name = "s2_analysis"

    def execute(self) -> StageResult:
        # Manual mode: check if result already exists
        result_path = self.workspace / "s2_analysis_result.json"
        if self.config.llm_mode == "manual":
            if result_path.exists():
                logger.info("Manual mode: loading existing s2_analysis_result.json")
                data = self.load_result("s2_analysis_result.json")
                return StageResult(stage_name=self.name, success=True, data=data)
            else:
                # Output what Claude Code needs to process
                s1_data = self.load_result("s1_input_result.json")
                self._save_prompt_data(s1_data)
                return StageResult(
                    stage_name=self.name,
                    success=False,
                    error=f"{MANUAL_PAUSE}: s2_analysis_result.json 파일이 필요합니다. "
                          f"Claude Code에서 workspace/{self.config.job_id}/s2_prompt.json을 "
                          f"참고하여 s2_analysis_result.json을 생성해주세요.",
                )

        # API mode
        s1_data = self.load_result("s1_input_result.json")
        input_mode = s1_data.get("input_mode", self.config.input_mode.value)

        if input_mode == "multi_url":
            return self._analyze_multi(s1_data)
        elif input_mode == "trending":
            return self._analyze_trending(s1_data)
        else:
            return self._analyze_youtube(s1_data)

    def _save_prompt_data(self, s1_data: dict):
        """Save formatted data for Claude Code to process."""
        import json

        input_mode = s1_data.get("input_mode", "url")

        prompt_data = {
            "stage": "s2_analysis",
            "instruction": "아래 데이터를 분석하여 s2_analysis_result.json을 생성해주세요.",
            "input_mode": input_mode,
            "output_schema": {
                "analysis": {
                    "summary": "영상 전체 요약 (2-3문장)",
                    "key_topics": ["주요 주제"],
                    "product_features": [{"name": "기능명", "description": "설명"}],
                    "target_audience": "대상 시청자",
                    "tone": "톤앤매너",
                    "concept": "핵심 컨셉",
                    "core_promise": "시청자가 얻는 가치",
                    "emotion_strategy": "감정 전략",
                    "segments": [{"topic": "", "summary": "", "key_points": []}],
                    "comment_analysis": {
                        "total_comments": 0,
                        "top_sentiments": [],
                        "key_opinions": [],
                        "content_requests": [],
                        "emotional_tone": "",
                    },
                }
            },
        }

        if input_mode == "multi_url":
            prompt_data["references"] = s1_data.get("references", [])
        elif input_mode == "trending":
            prompt_data["topic_title"] = s1_data.get("topic_title", "")
            prompt_data["research_text"] = s1_data.get("research_text", "")
        else:
            prompt_data["metadata"] = s1_data.get("metadata", {})
            prompt_data["transcript_text"] = s1_data.get("transcript_text", "")[:5000]
            prompt_data["comments"] = s1_data.get("comments", [])

        prompt_path = self.workspace / "s2_prompt.json"
        with open(prompt_path, "w", encoding="utf-8") as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved prompt data: {prompt_path}")

    def _analyze_youtube(self, s1_data: dict) -> StageResult:
        """Analyze single YouTube video with comments."""
        from autoworker_youtube.services import llm

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
        from autoworker_youtube.services import llm

        references = s1_data.get("references", [])
        if not references:
            return StageResult(
                stage_name=self.name, success=False, error="No reference data found"
            )

        analysis = llm.analyze_multi_references(
            references=references, language=self.config.language
        )

        data = {"analysis": analysis.model_dump()}
        self.save_result(data)
        return StageResult(stage_name=self.name, success=True, data=data)

    def _analyze_trending(self, s1_data: dict) -> StageResult:
        """Pass through trending data to Stage 3."""
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
