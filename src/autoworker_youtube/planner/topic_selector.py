"""Topic selection and research compilation for trending mode."""

from __future__ import annotations

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import LLMError
from autoworker_youtube.sources import google_news, google_trends


def discover_topics(
    region: str = "KR",
    category: str | None = None,
    topic: str | None = None,
    max_topics: int = 5,
) -> list[dict]:
    """Discover trending topics from multiple sources.

    Returns a ranked list of topics with metadata.
    """
    all_candidates = []

    # Source 1: Google Trends
    trends = google_trends.get_trending_searches(
        region="south_korea" if region == "KR" else region.lower()
    )
    all_candidates.extend(trends)

    # Source 2: Google News
    news = google_news.get_top_news(topic=topic or category, region=region)
    for item in news:
        all_candidates.append({
            "title": item["title"],
            "description": item.get("description", ""),
            "source": "google_news",
            "media": item.get("media", ""),
        })

    if not all_candidates:
        logger.warning("No trending candidates found from any source")
        return []

    # Use LLM to rank and select best topics for video creation
    return _rank_topics(all_candidates, category, max_topics)


def _rank_topics(
    candidates: list[dict],
    category: str | None,
    max_topics: int,
) -> list[dict]:
    """Use LLM to rank topics by video suitability."""
    import json

    import anthropic

    if not settings.anthropic_api_key:
        # Without LLM, return top candidates as-is
        return candidates[:max_topics]

    candidates_text = json.dumps(candidates[:30], ensure_ascii=False, indent=2)
    category_hint = f"\n선호 카테고리: {category}" if category else ""

    prompt = f"""다음 트렌딩 주제 후보들 중에서 YouTube 소개/설명 영상으로 만들기 가장 좋은 주제 {max_topics}개를 선정하세요.
{category_hint}

## 선정 기준
- 대중의 관심도가 높은 주제
- 영상으로 설명하기 적합한 주제
- 시각적 자료를 만들 수 있는 주제
- 시의성이 있는 주제

## 후보 목록
{candidates_text}

## 출력 형식 (JSON array)
[
    {{
        "title": "선정된 주제",
        "reason": "선정 이유",
        "video_angle": "이 주제를 영상으로 다룰 각도/관점",
        "suggested_title": "영상 제목 제안"
    }}
]

JSON만 출력하세요."""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=2048,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]
        return json.loads(content)
    except Exception as e:
        logger.warning(f"Topic ranking failed: {e}")
        return [{"title": c["title"], "reason": "auto-selected"} for c in candidates[:max_topics]]


def compile_research(topic: str, region: str = "KR") -> str:
    """Compile research material for a given topic from multiple sources."""
    logger.info(f"Compiling research for topic: {topic}")

    sections = []

    # Collect news articles
    news = google_news.get_top_news(topic=topic, region=region, max_results=5)
    if news:
        sections.append("## 관련 뉴스")
        for item in news:
            sections.append(f"### {item['title']}")
            sections.append(f"출처: {item.get('media', 'N/A')} | {item.get('date', '')}")
            sections.append(item.get("description", ""))
            # Try to get article detail
            if item.get("link"):
                detail = google_news.get_news_detail(item["link"])
                if detail:
                    sections.append(detail[:500])
            sections.append("")

    # Collect related trends
    related = google_trends.get_related_topics(topic, region=region)
    if related:
        sections.append("## 관련 트렌드 토픽")
        for item in related:
            sections.append(f"- {item.get('title', '')} ({item.get('type', '')})")
        sections.append("")

    research_text = "\n".join(sections)
    if not research_text.strip():
        research_text = f"주제: {topic}\n(자동 수집된 자료 없음 - LLM 기반 생성 진행)"

    logger.info(f"Compiled {len(research_text)} chars of research")
    return research_text
