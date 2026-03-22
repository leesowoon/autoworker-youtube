"""Shared data models for the pipeline."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VideoType(str, Enum):
    PRODUCT_INTRO = "product_intro"
    REVIEW = "review"
    TUTORIAL = "tutorial"
    NEWS = "news"


class InputMode(str, Enum):
    URL = "url"
    MULTI_URL = "multi_url"
    TRENDING = "trending"


class JobConfig(BaseModel):
    """Top-level configuration for a video generation job."""

    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    input_mode: InputMode = InputMode.URL
    youtube_url: str | None = None
    youtube_urls: list[str] = []  # multi-URL mode
    video_type: VideoType = VideoType.PRODUCT_INTRO
    language: str = "ko"
    target_duration_sec: int = 120
    resolution: tuple[int, int] = (1920, 1080)
    voice_id: str = "ko-KR-SunHiNeural"
    output_path: str | None = None
    output_format: str = "mp4"  # mp4 or capcut

    # Comment analysis
    include_comments: bool = True
    max_comments: int = 20

    # Title generation
    title_candidates: int = 3
    auto_select_title: bool = True

    # Image generation
    image_provider: str | None = None  # dalle, stability, grok, whisk, none (auto if None)

    # LLM mode: "api" (call Anthropic API) or "manual" (Claude Code fills JSON)
    llm_mode: str = "manual"

    # Trending mode options
    region: str = "KR"
    category: str | None = None
    topic: str | None = None

    # Batch mode
    channels: list[str] = []  # multiple channel generation


class VideoMetadata(BaseModel):
    """YouTube video metadata."""

    video_id: str
    title: str
    description: str
    channel: str
    channel_id: str = ""
    channel_url: str = ""
    tags: list[str] = []
    duration_sec: int = 0
    view_count: int = 0
    subscriber_count: int = 0
    thumbnail_url: str = ""
    upload_date: str = ""


class TranscriptSegment(BaseModel):
    """A single transcript segment with timing."""

    start: float
    duration: float
    text: str


class CommentAnalysis(BaseModel):
    """Analyzed comment data."""

    total_comments: int = 0
    top_sentiments: list[str] = []
    key_opinions: list[str] = []
    content_requests: list[str] = []
    emotional_tone: str = ""


class ContentSegment(BaseModel):
    """Analyzed content segment."""

    topic: str
    summary: str
    key_points: list[str] = []
    start_time: float | None = None
    end_time: float | None = None


class AnalysisReport(BaseModel):
    """Structured content analysis output."""

    summary: str
    key_topics: list[str] = []
    product_features: list[dict[str, Any]] = []
    target_audience: str = ""
    tone: str = ""
    segments: list[ContentSegment] = []
    source_type: str = "youtube"  # youtube | trending
    comment_analysis: CommentAnalysis | None = None
    concept: str = ""
    core_promise: str = ""  # 영상을 끝까지 들으면 얻는 것
    emotion_strategy: str = ""


class TitleCandidate(BaseModel):
    """A candidate video title with reasoning."""

    title: str
    style: str = ""  # 흥미유발, 정보전달, 감성, etc.
    reason: str = ""
    score: float = 0.0


class Scene(BaseModel):
    """A single scene in the video script."""

    scene_id: int
    type: str  # hook, problem, introduction, feature, demo, cta, outro, closing
    duration_sec: float
    narration: str
    visual_direction: str = ""
    text_overlay: str | None = None
    transition: str = "fade"
    image_prompt: str = ""  # AI image generation prompt


class VideoScript(BaseModel):
    """Complete video script with scenes."""

    title: str
    title_candidates: list[TitleCandidate] = []
    total_duration_sec: float
    scenes: list[Scene] = []
    concept: str = ""
    target_viewer: str = ""


class AssetManifest(BaseModel):
    """Tracks all generated assets for a job."""

    narration_files: list[str] = []
    image_files: list[str] = []
    subtitle_file: str | None = None
    bgm_file: str | None = None


class CapCutTrack(BaseModel):
    """A single track in a CapCut project."""

    type: str  # video, audio, text
    file_path: str
    start_time: float = 0.0
    duration: float = 0.0
    text: str = ""


class StageResult(BaseModel):
    """Result of a pipeline stage execution."""

    stage_name: str
    success: bool = True
    error: str | None = None
    data: dict[str, Any] = {}


class PipelineResult(BaseModel):
    """Final pipeline execution result."""

    job_id: str
    success: bool = True
    output_path: str | None = None
    stages: list[StageResult] = []
    error: str | None = None
