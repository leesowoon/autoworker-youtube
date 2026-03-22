"""YouTube trending videos source."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.models import VideoMetadata


def get_trending_videos(
    region: str = "KR",
    category: str | None = None,
    max_results: int = 10,
) -> list[VideoMetadata]:
    """Get trending YouTube videos using yt-dlp.

    Uses YouTube's trending page instead of API to avoid quota usage.
    """
    import json
    import subprocess

    url = f"https://www.youtube.com/feed/trending"
    if category:
        category_map = {
            "music": "10",
            "gaming": "20",
            "news": "25",
            "movies": "44",
        }
        cat_id = category_map.get(category.lower(), "")
        if cat_id:
            url = f"https://www.youtube.com/feed/trending?bp=6gQJRkVleHBsb3Jl"

    logger.info(f"Fetching YouTube trending videos for {region}...")

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                "--playlist-items", f"1:{max_results}",
                "--geo-bypass-country", region,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                info = json.loads(line)
                videos.append(
                    VideoMetadata(
                        video_id=info.get("id", ""),
                        title=info.get("title", ""),
                        description=info.get("description", ""),
                        channel=info.get("channel", info.get("uploader", "")),
                        tags=info.get("tags", []) or [],
                        duration_sec=int(info.get("duration", 0) or 0),
                        view_count=int(info.get("view_count", 0) or 0),
                        thumbnail_url=info.get("thumbnail", ""),
                    )
                )
            except (json.JSONDecodeError, TypeError):
                continue

        logger.info(f"Found {len(videos)} trending videos")
        return videos
    except Exception as e:
        logger.error(f"Trending videos fetch failed: {e}")
        return []
