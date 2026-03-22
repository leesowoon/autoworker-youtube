"""Stage 6: Output - final validation and cleanup."""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.models import StageResult
from autoworker_youtube.stages.base import StageBase


class OutputStage(StageBase):
    name = "s6_output"

    def execute(self) -> StageResult:
        s5_data = self.load_result("s5_assembly_result.json")
        output_path = Path(s5_data["output_path"])

        if not output_path.exists():
            return StageResult(
                stage_name=self.name,
                success=False,
                error=f"Output file not found: {output_path}",
            )

        file_size = os.path.getsize(output_path)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Output video: {output_path}")
        logger.info(f"File size: {file_size_mb:.1f} MB")

        # Load script info for summary
        try:
            s3_data = self.load_result("s3_script_result.json")
            title = s3_data["script"].get("title", "Untitled")
            duration = s3_data["script"].get("total_duration_sec", 0)
        except Exception:
            title = "Untitled"
            duration = 0

        data = {
            "output_path": str(output_path),
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size_mb, 1),
            "title": title,
            "target_duration_sec": duration,
        }
        self.save_result(data)

        return StageResult(stage_name=self.name, success=True, data=data)
