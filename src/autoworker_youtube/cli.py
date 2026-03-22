"""CLI interface using Typer."""

from __future__ import annotations

import os
from typing import Optional

import typer
from loguru import logger

from autoworker_youtube.core.models import InputMode, JobConfig, VideoType

app = typer.Typer(
    name="autoworker-youtube",
    help="Auto-generate videos from YouTube URLs or trending topics.",
)

MANUAL_PAUSE = "MANUAL_LLM_PAUSE"


def _resolve_llm_mode(llm_mode: str) -> str:
    """Resolve 'auto' llm_mode based on API key availability."""
    if llm_mode == "auto":
        if os.getenv("ANTHROPIC_API_KEY"):
            return "api"
        return "manual"
    return llm_mode


@app.command()
def generate(
    urls: list[str] = typer.Argument(..., help="YouTube URL(s) to use as reference"),
    video_type: str = typer.Option("product_intro", "--type", "-t", help="Video type: product_intro, review, tutorial, news"),
    duration: int = typer.Option(120, "--duration", "-d", help="Target video duration in seconds"),
    language: str = typer.Option("ko", "--lang", "-l", help="Language code"),
    voice: str = typer.Option("ko-KR-SunHiNeural", "--voice", "-v", help="TTS voice ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    output_format: str = typer.Option("mp4", "--format", "-f", help="Output format: mp4 or capcut"),
    no_comments: bool = typer.Option(False, "--no-comments", help="Skip comment analysis"),
    titles: int = typer.Option(3, "--titles", help="Number of title candidates to generate"),
    no_auto_title: bool = typer.Option(False, "--no-auto-title", help="Don't auto-select title (show candidates)"),
    image_provider: Optional[str] = typer.Option(None, "--image", "-i", help="Image provider: dalle, stability, grok, whisk, none"),
    llm_mode: str = typer.Option("auto", "--llm-mode", help="LLM mode: api, manual, auto"),
):
    """Generate a video from one or more YouTube URLs."""
    if len(urls) == 1:
        mode = InputMode.URL
    else:
        mode = InputMode.MULTI_URL

    config = JobConfig(
        input_mode=mode,
        youtube_url=urls[0] if len(urls) == 1 else None,
        youtube_urls=urls if len(urls) > 1 else [],
        video_type=VideoType(video_type),
        target_duration_sec=duration,
        language=language,
        voice_id=voice,
        output_path=output,
        output_format=output_format,
        include_comments=not no_comments,
        image_provider=image_provider,
        title_candidates=titles,
        auto_select_title=not no_auto_title,
        llm_mode=_resolve_llm_mode(llm_mode),
    )

    _run_pipeline(config)


@app.command()
def discover(
    region: str = typer.Option("KR", "--region", "-r", help="Region code (KR, US, JP, etc.)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category filter"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Specific topic to search for"),
    count: int = typer.Option(5, "--count", "-n", help="Number of topics to discover"),
):
    """Discover trending topics without generating a video."""
    from autoworker_youtube.planner.topic_selector import discover_topics

    logger.info(f"Discovering trending topics for {region}...")
    topics = discover_topics(region=region, category=category, topic=topic, max_topics=count)

    if not topics:
        typer.echo("No trending topics found.")
        raise typer.Exit(1)

    typer.echo(f"\n{'='*60}")
    typer.echo(f"  Trending Topics ({region})")
    typer.echo(f"{'='*60}")
    for i, t in enumerate(topics, 1):
        title = t.get("title", t.get("suggested_title", "N/A"))
        reason = t.get("reason", "")
        angle = t.get("video_angle", "")
        typer.echo(f"\n  {i}. {title}")
        if reason:
            typer.echo(f"     이유: {reason}")
        if angle:
            typer.echo(f"     영상 각도: {angle}")
    typer.echo(f"\n{'='*60}")


@app.command()
def find_channels(
    keyword: str = typer.Argument(..., help="Search keyword for finding channels"),
    count: int = typer.Option(20, "--count", "-n", help="Number of results"),
    min_views: int = typer.Option(10000, "--min-views", help="Minimum view count filter"),
):
    """Find channels with high view-to-subscriber ratio (뜨는 채널 찾기)."""
    from autoworker_youtube.services.youtube import find_efficient_channels

    typer.echo(f"\nSearching for efficient channels: '{keyword}'...")
    results = find_efficient_channels(keyword, max_results=count, min_views=min_views)

    if not results:
        typer.echo("No results found.")
        raise typer.Exit(1)

    typer.echo(f"\n{'='*80}")
    typer.echo(f"  뜨는 채널 찾기: '{keyword}' (조회수/구독자 효율 순)")
    typer.echo(f"{'='*80}")

    for i, v in enumerate(results, 1):
        eff = v['efficiency']
        views = v['view_count']
        subs = v['subscriber_count']
        typer.echo(f"\n  {i}. [{eff:.1f}x] {v['title'][:60]}")
        typer.echo(f"     채널: {v['channel']}")
        typer.echo(f"     조회수: {views:,} | 구독자: {subs:,} | 효율: {eff:.1f}배")
        typer.echo(f"     URL: {v['url']}")

    typer.echo(f"\n{'='*80}")
    typer.echo(f"  Total: {len(results)} videos found")
    typer.echo(f"{'='*80}")


@app.command()
def auto(
    region: str = typer.Option("KR", "--region", "-r", help="Region code"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category filter"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Specific topic"),
    duration: int = typer.Option(120, "--duration", "-d", help="Target duration in seconds"),
    video_type: str = typer.Option("news", "--type", help="Video type"),
    voice: str = typer.Option("ko-KR-SunHiNeural", "--voice", "-v", help="TTS voice ID"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    output_format: str = typer.Option("mp4", "--format", "-f", help="Output format: mp4 or capcut"),
    image_provider: Optional[str] = typer.Option(None, "--image", "-i", help="Image provider: dalle, stability, grok, whisk, none"),
    llm_mode: str = typer.Option("auto", "--llm-mode", help="LLM mode: api, manual, auto"),
):
    """Auto-discover a trending topic and generate a video."""
    config = JobConfig(
        input_mode=InputMode.TRENDING,
        video_type=VideoType(video_type),
        target_duration_sec=duration,
        voice_id=voice,
        output_path=output,
        output_format=output_format,
        region=region,
        category=category,
        topic=topic,
        image_provider=image_provider,
        llm_mode=_resolve_llm_mode(llm_mode),
    )

    _run_pipeline(config)


@app.command()
def batch(
    urls_file: str = typer.Argument(..., help="File with YouTube URLs (one per line)"),
    video_type: str = typer.Option("product_intro", "--type", "-t"),
    duration: int = typer.Option(120, "--duration", "-d"),
    output_format: str = typer.Option("mp4", "--format", "-f", help="Output format: mp4 or capcut"),
    llm_mode: str = typer.Option("auto", "--llm-mode", help="LLM mode: api, manual, auto"),
):
    """Batch generate videos from a file of YouTube URLs (like multi-channel)."""
    from pathlib import Path

    urls_path = Path(urls_file)
    if not urls_path.exists():
        typer.echo(f"File not found: {urls_file}")
        raise typer.Exit(1)

    urls = [line.strip() for line in urls_path.read_text().splitlines() if line.strip()]
    typer.echo(f"\n Processing {len(urls)} videos...")

    for i, url in enumerate(urls, 1):
        typer.echo(f"\n{'='*60}")
        typer.echo(f"  [{i}/{len(urls)}] {url}")
        typer.echo(f"{'='*60}")

        config = JobConfig(
            input_mode=InputMode.URL,
            youtube_url=url,
            video_type=VideoType(video_type),
            target_duration_sec=duration,
            output_format=output_format,
            llm_mode=_resolve_llm_mode(llm_mode),
        )

        try:
            _run_pipeline(config)
        except SystemExit:
            typer.echo(f"  Failed for: {url}")
            continue


@app.command()
def episode(
    episode_file: str = typer.Argument(..., help="Episode JSON file path"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output video path"),
    no_animate: bool = typer.Option(False, "--no-animate", help="Skip Grok video animation"),
    voice: str = typer.Option("ko-KR-SunHiNeural", "--voice", "-v", help="TTS voice"),
    voice_rate: str = typer.Option("-15%", "--rate", help="TTS speed (e.g. -15%, +0%)"),
    assets_dir: Optional[str] = typer.Option(None, "--assets", help="Character sheets directory"),
):
    """Generate a Bori Universe episode from an episode JSON file."""
    from pathlib import Path

    from autoworker_youtube.universe.episode import generate_episode
    from autoworker_youtube.universe.world import BoriUniverse

    ep_path = Path(episode_file)
    if not ep_path.exists():
        typer.echo(f"Episode file not found: {episode_file}")
        raise typer.Exit(1)

    import json
    with open(ep_path, encoding="utf-8") as f:
        ep_data = json.load(f)

    title = ep_data.get("title", "Untitled")
    scenes = ep_data.get("scenes", [])
    typer.echo(f"\n Episode: {title}")
    typer.echo(f" Scenes: {len(scenes)}")
    typer.echo(f" Animate: {'OFF' if no_animate else 'ON'}")
    typer.echo(f" Voice: {voice} ({voice_rate})")
    typer.echo("")

    universe = BoriUniverse(
        assets_dir=Path(assets_dir) if assets_dir else None
    )

    work_dir = Path(f"workspace/episodes/{_safe_ep_name(title)}")
    work_dir.mkdir(parents=True, exist_ok=True)

    out_path = Path(output) if output else None
    result = generate_episode(
        episode_data=ep_data,
        output_dir=work_dir,
        output_path=out_path,
        universe=universe,
        animate=not no_animate,
        voice=voice,
        voice_rate=voice_rate,
    )

    if result:
        typer.echo(f"\n Episode generated: {result}")
    else:
        typer.echo(f"\n Episode generation failed")
        raise typer.Exit(1)


def _safe_ep_name(text: str) -> str:
    import re
    safe = re.sub(r'[^\w\s가-힣-]', '', text)
    return safe.strip().replace(' ', '_')[:30]


@app.command()
def resume(
    job_id: str = typer.Argument(..., help="Job ID to resume"),
    stage: int = typer.Option(0, "--stage", "-s", help="Stage index to resume from (0-5)"),
):
    """Resume a failed/paused pipeline from a specific stage."""
    import json
    from pathlib import Path

    from autoworker_youtube.core.config import settings

    workspace = settings.get_workspace_path(job_id)
    config_path = workspace / "job_config.json"

    if config_path.exists():
        with open(config_path) as f:
            config = JobConfig(**json.load(f))
    else:
        typer.echo(f"No saved config found for job {job_id}")
        raise typer.Exit(1)

    _run_pipeline(config, from_stage=stage)


def _run_pipeline(config: JobConfig, from_stage: int = 0):
    """Run the pipeline with the given config."""
    import json

    from autoworker_youtube.core.config import settings
    from autoworker_youtube.core.pipeline import Pipeline

    # Save job config for resume
    workspace = settings.get_workspace_path(config.job_id)
    config_path = workspace / "job_config.json"
    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)

    typer.echo(f"\n Job ID: {config.job_id}")
    typer.echo(f" Mode: {config.input_mode.value}")
    typer.echo(f" LLM: {config.llm_mode}")
    if config.youtube_url:
        typer.echo(f" URL: {config.youtube_url}")
    if config.youtube_urls:
        typer.echo(f" URLs: {len(config.youtube_urls)} references")
        for u in config.youtube_urls:
            typer.echo(f"   - {u}")
    if config.topic:
        typer.echo(f" Topic: {config.topic}")
    typer.echo(f" Duration: {config.target_duration_sec}s")
    typer.echo(f" Format: {config.output_format}")
    typer.echo("")

    pipeline = Pipeline(config)
    result = pipeline.run(from_stage=from_stage)

    if result.success:
        typer.echo(f"\n Video generated successfully!")
        typer.echo(f" Output: {result.output_path}")

        # Show title candidates if available
        try:
            s3_data = json.loads(
                (workspace / "s3_script_result.json").read_text()
            )
            candidates = s3_data["script"].get("title_candidates", [])
            if candidates:
                typer.echo(f"\n Title candidates:")
                for tc in candidates:
                    marker = " <-- selected" if tc["title"] == s3_data["script"]["title"] else ""
                    typer.echo(f"   [{tc.get('score', 0)}] {tc['title']}{marker}")
        except Exception:
            pass

    elif result.error and result.error.startswith(MANUAL_PAUSE):
        # Manual LLM pause - not a failure
        typer.echo(f"\n Pipeline paused - Claude Code LLM 처리 필요")
        typer.echo(f" Workspace: {workspace}")
        typer.echo(f"")
        typer.echo(f" 다음 단계:")
        typer.echo(f"   1. Claude Code에서 프롬프트 데이터를 읽고 결과 JSON 생성")
        typer.echo(f"   2. 완료 후: autoworker resume {config.job_id} --stage 3")
        typer.echo(f"      (s3도 완료된 경우: autoworker resume {config.job_id} --stage 3)")
    else:
        typer.echo(f"\n Pipeline failed: {result.error}")
        typer.echo(f" Resume with: autoworker resume {config.job_id}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
