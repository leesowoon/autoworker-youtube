"""YouTube data extraction service."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import InputError, TranscriptError
from autoworker_youtube.core.models import TranscriptSegment, VideoMetadata


def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise InputError(f"Cannot extract video ID from URL: {url}")


def fetch_metadata(video_id: str) -> VideoMetadata:
    """Fetch video metadata using yt-dlp (no API key needed)."""
    logger.info(f"Fetching metadata for video: {video_id}")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise InputError(f"yt-dlp failed: {result.stderr}")

        info = json.loads(result.stdout)
        return VideoMetadata(
            video_id=video_id,
            title=info.get("title", ""),
            description=info.get("description", ""),
            channel=info.get("channel", info.get("uploader", "")),
            channel_id=info.get("channel_id", ""),
            channel_url=info.get("channel_url", ""),
            tags=info.get("tags", []) or [],
            duration_sec=int(info.get("duration", 0)),
            view_count=int(info.get("view_count", 0)),
            subscriber_count=int(info.get("channel_follower_count", 0) or 0),
            thumbnail_url=info.get("thumbnail", ""),
            upload_date=info.get("upload_date", ""),
        )
    except subprocess.TimeoutExpired:
        raise InputError("Metadata fetch timed out")
    except json.JSONDecodeError:
        raise InputError("Failed to parse yt-dlp output")


def fetch_transcript(video_id: str, language: str = "ko") -> list[TranscriptSegment]:
    """Fetch transcript with language fallback."""
    logger.info(f"Fetching transcript for video: {video_id} (lang={language})")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt = YouTubeTranscriptApi()

        # Try preferred language first, then fallback
        try:
            result = ytt.fetch(video_id, languages=[language])
            snippets = result.snippets
        except Exception:
            logger.warning(f"No {language} transcript, trying fallback...")
            try:
                result = ytt.fetch(video_id, languages=[language, "en"])
                snippets = result.snippets
            except Exception:
                # Last resort: get any available transcript
                transcript_list = ytt.list(video_id)
                for t in transcript_list:
                    try:
                        result = ytt.fetch(video_id, languages=[t.language_code])
                        snippets = result.snippets
                        break
                    except Exception:
                        continue
                else:
                    raise TranscriptError("No transcript available")

        return [
            TranscriptSegment(
                start=seg.start,
                duration=seg.duration,
                text=seg.text,
            )
            for seg in snippets
        ]
    except ImportError:
        raise TranscriptError("youtube-transcript-api not installed")
    except TranscriptError:
        raise
    except Exception as e:
        raise TranscriptError(f"Failed to fetch transcript: {e}")


def fetch_comments(video_id: str, max_comments: int = 30) -> list[dict]:
    """Fetch top comments from a YouTube video using yt-dlp."""
    logger.info(f"Fetching comments for video: {video_id}")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-comments",
                "--no-download",
                "--dump-json",
                "--extractor-args",
                f"youtube:max_comments={max_comments},all,100",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(f"Comment fetch failed: {result.stderr[:200]}")
            return []

        info = json.loads(result.stdout)
        raw_comments = info.get("comments", [])

        comments = []
        for c in raw_comments[:max_comments]:
            comments.append({
                "author": c.get("author", ""),
                "text": c.get("text", ""),
                "likes": c.get("like_count", 0),
                "is_favorited": c.get("is_favorited", False),
            })

        # Sort by likes (most popular first)
        comments.sort(key=lambda x: x.get("likes", 0), reverse=True)
        logger.info(f"Fetched {len(comments)} comments")
        return comments
    except Exception as e:
        logger.warning(f"Comment fetch error: {e}")
        return []


def download_thumbnail(video_id: str, output_dir: Path) -> Path | None:
    """Download video thumbnail."""
    output_path = output_dir / f"thumbnail_{video_id}.jpg"
    try:
        subprocess.run(
            [
                "yt-dlp",
                "--write-thumbnail",
                "--skip-download",
                "--convert-thumbnails", "jpg",
                "-o", str(output_dir / f"thumbnail_{video_id}"),
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            timeout=15,
        )
        # yt-dlp may add various extensions
        for ext in [".jpg", ".webp", ".png"]:
            candidate = output_dir / f"thumbnail_{video_id}{ext}"
            if candidate.exists():
                if ext != ".jpg":
                    candidate.rename(output_path)
                return output_path
        return None
    except Exception as e:
        logger.warning(f"Thumbnail download failed: {e}")
        return None


def download_audio(video_id: str, output_dir: Path) -> Path:
    """Download audio track for STT fallback."""
    output_path = output_dir / f"{video_id}.mp3"
    logger.info(f"Downloading audio to: {output_path}")
    subprocess.run(
        [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", str(output_path),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        capture_output=True,
        timeout=120,
        check=True,
    )
    return output_path


def search_videos(query: str, max_results: int = 5, language: str = "ko") -> list[VideoMetadata]:
    """Search YouTube for videos matching a query using yt-dlp."""
    logger.info(f"Searching YouTube for: {query}")
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--flat-playlist",
                f"ytsearch{max_results}:{query}",
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
                        channel_id=info.get("channel_id", ""),
                        tags=info.get("tags", []) or [],
                        duration_sec=int(info.get("duration", 0) or 0),
                        view_count=int(info.get("view_count", 0) or 0),
                        subscriber_count=int(info.get("channel_follower_count", 0) or 0),
                        thumbnail_url=info.get("thumbnail", ""),
                    )
                )
            except (json.JSONDecodeError, TypeError):
                continue
        return videos
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
        return []


def find_efficient_channels(
    keyword: str,
    max_results: int = 20,
    min_views: int = 10000,
) -> list[dict]:
    """Find channels with high view-to-subscriber ratio (뜨는 채널 찾기).

    Searches for videos matching the keyword, then ranks channels by
    efficiency = view_count / subscriber_count.
    """
    logger.info(f"Finding efficient channels for keyword: {keyword}")

    # Search for videos with full metadata
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                f"ytsearch{max_results}:{keyword}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        logger.error("Channel search timed out")
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            info = json.loads(line)
            view_count = int(info.get("view_count", 0) or 0)
            sub_count = int(info.get("channel_follower_count", 0) or 0)

            if view_count < min_views:
                continue

            efficiency = view_count / max(sub_count, 1)

            videos.append({
                "video_id": info.get("id", ""),
                "title": info.get("title", ""),
                "channel": info.get("channel", info.get("uploader", "")),
                "channel_id": info.get("channel_id", ""),
                "channel_url": info.get("channel_url", ""),
                "view_count": view_count,
                "subscriber_count": sub_count,
                "duration_sec": int(info.get("duration", 0) or 0),
                "upload_date": info.get("upload_date", ""),
                "efficiency": round(efficiency, 2),
                "url": f"https://www.youtube.com/watch?v={info.get('id', '')}",
            })
        except (json.JSONDecodeError, TypeError):
            continue

    # Sort by efficiency (highest first)
    videos.sort(key=lambda x: x["efficiency"], reverse=True)

    logger.info(f"Found {len(videos)} videos, ranked by efficiency")
    return videos


def fetch_multi_video_data(
    urls: list[str],
    language: str = "ko",
    include_comments: bool = True,
    max_comments: int = 20,
) -> list[dict]:
    """Fetch metadata, transcript, and comments for multiple videos.

    This is the core of the multi-reference analysis pipeline.
    """
    logger.info(f"Fetching data for {len(urls)} reference videos...")
    results = []

    for url in urls:
        video_id = extract_video_id(url)
        data = {"url": url, "video_id": video_id}

        # Metadata
        try:
            metadata = fetch_metadata(video_id)
            data["metadata"] = metadata.model_dump()
        except Exception as e:
            logger.warning(f"Metadata failed for {video_id}: {e}")
            data["metadata"] = {"title": "", "video_id": video_id}

        # Transcript
        try:
            transcript = fetch_transcript(video_id, language)
            data["transcript_text"] = " ".join(seg.text for seg in transcript)
            data["transcript_segments"] = [s.model_dump() for s in transcript]
        except Exception as e:
            logger.warning(f"Transcript failed for {video_id}: {e}")
            data["transcript_text"] = ""
            data["transcript_segments"] = []

        # Comments
        if include_comments:
            data["comments"] = fetch_comments(video_id, max_comments)
        else:
            data["comments"] = []

        results.append(data)

    return results
