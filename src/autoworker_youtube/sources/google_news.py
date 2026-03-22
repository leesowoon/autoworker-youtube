"""Google News data source."""

from __future__ import annotations

from loguru import logger


def get_top_news(
    topic: str | None = None,
    language: str = "ko",
    region: str = "KR",
    max_results: int = 10,
) -> list[dict]:
    """Get top news articles from Google News.

    Args:
        topic: Optional search topic. If None, returns top headlines.
        language: Language code.
        region: Region code.
        max_results: Maximum number of results.

    Returns:
        List of dicts with 'title', 'description', 'link', 'date', 'media'.
    """
    try:
        from GoogleNews import GoogleNews

        gn = GoogleNews(lang=language, region=region, period="1d")

        if topic:
            gn.search(topic)
        else:
            gn.get_news()

        results = []
        for item in gn.results()[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "description": item.get("desc", ""),
                "link": item.get("link", ""),
                "date": item.get("date", ""),
                "media": item.get("media", ""),
                "source": "google_news",
            })

        gn.clear()
        logger.info(f"Found {len(results)} news articles")
        return results
    except Exception as e:
        logger.warning(f"Google News fetch failed: {e}")
        return []


def get_news_detail(url: str) -> str:
    """Fetch article text from a news URL (best-effort)."""
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Simple text extraction (strip tags)
        import re

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception as e:
        logger.warning(f"News detail fetch failed: {e}")
        return ""
