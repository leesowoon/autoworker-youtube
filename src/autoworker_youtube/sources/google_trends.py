"""Google Trends data source using pytrends."""

from __future__ import annotations

from loguru import logger


def get_trending_searches(region: str = "south_korea") -> list[dict]:
    """Get current trending searches from Google Trends.

    Returns list of dicts with 'title' and 'traffic' keys.
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540)
        trending = pytrends.trending_searches(pn=region)

        results = []
        for _, row in trending.iterrows():
            results.append({"title": row[0], "source": "google_trends"})

        logger.info(f"Found {len(results)} trending searches from Google Trends")
        return results
    except Exception as e:
        logger.warning(f"Google Trends fetch failed: {e}")
        return []


def get_related_topics(keyword: str, region: str = "KR") -> list[dict]:
    """Get topics related to a keyword."""
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ko", tz=540)
        pytrends.build_payload([keyword], geo=region, timeframe="now 7-d")
        related = pytrends.related_topics()

        results = []
        if keyword in related:
            top = related[keyword].get("top")
            if top is not None and not top.empty:
                for _, row in top.head(10).iterrows():
                    results.append({
                        "title": row.get("topic_title", ""),
                        "type": row.get("topic_type", ""),
                        "value": int(row.get("value", 0)),
                    })
        return results
    except Exception as e:
        logger.warning(f"Related topics fetch failed: {e}")
        return []
