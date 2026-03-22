"""Pipeline orchestrator - runs all stages in sequence."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.models import JobConfig, PipelineResult, StageResult
from autoworker_youtube.stages.s1_input import InputStage
from autoworker_youtube.stages.s2_analysis import AnalysisStage
from autoworker_youtube.stages.s3_script import ScriptStage
from autoworker_youtube.stages.s4_assets import AssetStage
from autoworker_youtube.stages.s5_assembly import AssemblyStage
from autoworker_youtube.stages.s6_output import OutputStage


STAGE_CLASSES = [
    InputStage,
    AnalysisStage,
    ScriptStage,
    AssetStage,
    AssemblyStage,
    OutputStage,
]


class Pipeline:
    """Orchestrates the full video generation pipeline."""

    def __init__(self, config: JobConfig):
        self.config = config
        self.stages = [cls(config) for cls in STAGE_CLASSES]

    def run(self, from_stage: int = 0) -> PipelineResult:
        """Run the pipeline from a given stage index.

        Args:
            from_stage: Stage index to start from (0-based). Useful for resuming.

        Returns:
            PipelineResult with overall success/failure and per-stage results.
        """
        logger.info(f"═══ Pipeline starting (job={self.config.job_id}) ═══")
        logger.info(f"Mode: {self.config.input_mode.value}")
        if self.config.youtube_url:
            logger.info(f"URL: {self.config.youtube_url}")
        if self.config.topic:
            logger.info(f"Topic: {self.config.topic}")

        results: list[StageResult] = []

        for i, stage in enumerate(self.stages):
            if i < from_stage:
                logger.info(f"⏭ Skipping stage [{stage.name}]")
                continue

            result = stage.run()
            results.append(result)

            if not result.success:
                logger.error(f"Pipeline failed at stage [{stage.name}]")
                return PipelineResult(
                    job_id=self.config.job_id,
                    success=False,
                    stages=results,
                    error=f"Failed at {stage.name}: {result.error}",
                )

        # Extract output path from last stage
        output_path = None
        if results and results[-1].data:
            output_path = results[-1].data.get("output_path")

        logger.info(f"═══ Pipeline completed (job={self.config.job_id}) ═══")
        if output_path:
            logger.info(f"Output: {output_path}")

        return PipelineResult(
            job_id=self.config.job_id,
            success=True,
            output_path=output_path,
            stages=results,
        )

    def run_single_stage(self, stage_index: int) -> StageResult:
        """Run a single stage by index (for debugging)."""
        if stage_index < 0 or stage_index >= len(self.stages):
            return StageResult(
                stage_name=f"stage_{stage_index}",
                success=False,
                error=f"Invalid stage index: {stage_index}",
            )
        return self.stages[stage_index].run()
