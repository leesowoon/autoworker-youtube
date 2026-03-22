"""Application configuration loaded from environment and YAML."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


def _load_yaml_defaults() -> dict:
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "default.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


_yaml = _load_yaml_defaults()


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # API Keys
    youtube_api_key: str = ""
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    news_api_key: str = ""
    openai_api_key: str = ""
    stability_api_key: str = ""
    xai_api_key: str = ""

    # Paths
    workspace_dir: str = "./workspace"
    project_root: str = str(Path(__file__).parent.parent.parent.parent)

    # Defaults
    default_language: str = "ko"
    default_video_type: str = "product_intro"
    default_duration: int = 120
    default_voice: str = "ko-KR-SunHiNeural"

    # LLM
    llm_provider: str = Field(default=_yaml.get("llm", {}).get("provider", "anthropic"))
    llm_model: str = Field(default=_yaml.get("llm", {}).get("model", "claude-sonnet-4-20250514"))
    llm_max_tokens: int = Field(default=_yaml.get("llm", {}).get("max_tokens", 4096))
    llm_temperature: float = Field(default=_yaml.get("llm", {}).get("temperature", 0.7))

    # Video
    video_fps: int = Field(default=_yaml.get("video", {}).get("fps", 30))
    video_crf: int = Field(default=_yaml.get("video", {}).get("crf", 23))

    # TTS
    tts_provider: str = Field(default=_yaml.get("tts", {}).get("provider", "edge-tts"))
    tts_voice: str = Field(default=_yaml.get("tts", {}).get("voice", "ko-KR-SunHiNeural"))
    tts_rate: str = Field(default=_yaml.get("tts", {}).get("rate", "+0%"))

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_workspace_path(self, job_id: str) -> Path:
        base = Path(self.workspace_dir)
        job_path = base / job_id
        job_path.mkdir(parents=True, exist_ok=True)
        return job_path

    def get_job_subdir(self, job_id: str, subdir: str) -> Path:
        path = self.get_workspace_path(job_id) / subdir
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
