"""Base class for pipeline stages."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.models import JobConfig, StageResult


class StageBase(ABC):
    """Abstract base class for all pipeline stages."""

    name: str = "base"

    def __init__(self, config: JobConfig):
        self.config = config
        self.workspace = settings.get_workspace_path(config.job_id)

    @abstractmethod
    def execute(self) -> StageResult:
        """Execute this stage."""
        ...

    def save_result(self, data: dict, filename: str | None = None) -> Path:
        """Save stage result data as JSON."""
        filename = filename or f"{self.name}_result.json"
        path = self.workspace / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def load_result(self, filename: str) -> dict:
        """Load a previously saved stage result."""
        path = self.workspace / filename
        if not path.exists():
            raise FileNotFoundError(f"Result file not found: {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def get_subdir(self, name: str) -> Path:
        """Get a subdirectory in the workspace."""
        return settings.get_job_subdir(self.config.job_id, name)

    def run(self) -> StageResult:
        """Run with error handling and logging."""
        logger.info(f"▶ Stage [{self.name}] starting...")
        try:
            result = self.execute()
            if result.success:
                logger.info(f"✓ Stage [{self.name}] completed")
            else:
                logger.error(f"✗ Stage [{self.name}] failed: {result.error}")
            return result
        except Exception as e:
            logger.exception(f"✗ Stage [{self.name}] crashed")
            return StageResult(stage_name=self.name, success=False, error=str(e))
