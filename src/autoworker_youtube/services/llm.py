"""LLM service for content analysis and script generation."""

from __future__ import annotations

import json

from loguru import logger

from autoworker_youtube.core.config import settings
from autoworker_youtube.core.exceptions import LLMError
from autoworker_youtube.core.models import (
    AnalysisReport,
    CommentAnalysis,
    TitleCandidate,
    VideoScript,
)


def _get_client():
    """Get Anthropic client."""
    import anthropic

    if not settings.anthropic_api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _call_llm(prompt: str, max_tokens: int | None = None) -> str:
    """Call LLM and return parsed text, stripping markdown code fences."""
    client = _get_client()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens or settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]
    return content


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response with error handling."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Failed to parse LLM response as JSON: {e}\nResponse: {text[:500]}")


def analyze_content(
    transcript_text: str,
    metadata_summary: str,
    comments_text: str = "",
    language: str = "ko",
) -> AnalysisReport:
    """Analyze video content including comments and produce a structured report."""
    logger.info("Analyzing content with LLM...")

    comments_section = ""
    if comments_text:
        comments_section = f"""
## 댓글 반응 (인기순)
{comments_text}
"""

    prompt = f"""다음 YouTube 영상의 트랜스크립트, 메타데이터, 댓글을 분석하여 구조화된 보고서를 JSON으로 작성하세요.

## 메타데이터
{metadata_summary}

## 트랜스크립트
{transcript_text[:8000]}
{comments_section}
## 출력 형식 (JSON)
{{
    "summary": "영상 전체 요약 (2-3문장)",
    "key_topics": ["주요 주제 1", "주요 주제 2"],
    "product_features": [
        {{"name": "기능명", "description": "설명"}}
    ],
    "target_audience": "대상 시청자 설명",
    "tone": "영상의 톤앤매너",
    "concept": "이 영상의 핵심 컨셉 (한 줄)",
    "core_promise": "영상을 끝까지 보면 시청자가 얻는 것",
    "emotion_strategy": "댓글 반응 1위 감정과 이를 활용한 전략",
    "segments": [
        {{
            "topic": "세그먼트 주제",
            "summary": "세그먼트 요약",
            "key_points": ["포인트 1", "포인트 2"]
        }}
    ],
    "comment_analysis": {{
        "total_comments": {len(comments_text.split(chr(10))) if comments_text else 0},
        "top_sentiments": ["감성 1", "감성 2"],
        "key_opinions": ["주요 의견 1", "주요 의견 2"],
        "content_requests": ["시청자 요청사항"],
        "emotional_tone": "전체 감정 톤"
    }}
}}

JSON만 출력하세요. 마크다운 코드블록 없이 순수 JSON만 반환하세요."""

    try:
        content = _call_llm(prompt)
        data = _parse_json(content)
        return AnalysisReport(**data)
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"LLM analysis failed: {e}")


def analyze_multi_references(
    references: list[dict],
    language: str = "ko",
) -> AnalysisReport:
    """Analyze multiple reference videos and their comments together."""
    logger.info(f"Analyzing {len(references)} reference videos...")

    ref_sections = []
    for i, ref in enumerate(references, 1):
        meta = ref.get("metadata", {})
        transcript = ref.get("transcript_text", "")[:3000]
        comments = ref.get("comments", [])

        section = f"""### 레퍼런스 영상 {i}
제목: {meta.get('title', 'N/A')}
채널: {meta.get('channel', 'N/A')}
조회수: {meta.get('view_count', 0):,}
구독자: {meta.get('subscriber_count', 0):,}

트랜스크립트 (요약):
{transcript}
"""
        if comments:
            top_comments = "\n".join(
                f"- [{c.get('likes', 0)}좋아요] {c.get('text', '')}"
                for c in comments[:10]
            )
            section += f"\n인기 댓글:\n{top_comments}\n"

        ref_sections.append(section)

    all_refs = "\n".join(ref_sections)

    prompt = f"""다음 {len(references)}개의 YouTube 레퍼런스 영상을 종합 분석하세요.
이 영상들을 참고하여 새로운 영상을 만들 계획입니다.

{all_refs}

## 종합 분석 출력 (JSON)
{{
    "summary": "레퍼런스 영상들의 공통 주제 요약 (2-3문장)",
    "key_topics": ["공통 주요 주제들"],
    "product_features": [
        {{"name": "핵심 포인트", "description": "설명"}}
    ],
    "target_audience": "타겟 시청자",
    "tone": "권장 톤앤매너",
    "concept": "새 영상의 핵심 컨셉",
    "core_promise": "시청자가 영상에서 얻을 수 있는 가치",
    "emotion_strategy": "댓글 분석 기반 감정 전략 (어떤 감정을 자극할 것인지)",
    "segments": [
        {{"topic": "다룰 주제", "summary": "어떻게 다룰지", "key_points": ["포인트"]}}
    ],
    "comment_analysis": {{
        "total_comments": 0,
        "top_sentiments": ["댓글에서 발견된 주요 감정들"],
        "key_opinions": ["시청자들의 핵심 의견"],
        "content_requests": ["시청자들이 더 보고 싶어하는 내용"],
        "emotional_tone": "전체 감정 톤"
    }}
}}

JSON만 출력하세요."""

    try:
        content = _call_llm(prompt, max_tokens=4096)
        data = _parse_json(content)
        return AnalysisReport(**data)
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Multi-reference analysis failed: {e}")


def generate_script(
    analysis: AnalysisReport,
    video_type: str = "product_intro",
    target_duration: int = 120,
    language: str = "ko",
    num_title_candidates: int = 3,
    auto_select: bool = True,
) -> VideoScript:
    """Generate a video script with multiple title candidates."""
    logger.info(f"Generating {video_type} script ({target_duration}s)...")

    analysis_json = analysis.model_dump_json(indent=2)

    comment_hint = ""
    if analysis.comment_analysis:
        comment_hint = f"""
## 댓글 분석 결과 반영
- 주요 감정: {', '.join(analysis.comment_analysis.top_sentiments)}
- 감정 톤: {analysis.comment_analysis.emotional_tone}
- 시청자 요청: {', '.join(analysis.comment_analysis.content_requests)}
이 감정과 요청을 스크립트에 반영하세요.
"""

    prompt = f"""다음 콘텐츠 분석을 기반으로 {target_duration}초 길이의 영상 스크립트를 생성하세요.

## 영상 유형: {video_type}
## 목표 길이: {target_duration}초

## 콘텐츠 분석
{analysis_json}
{comment_hint}
## 중요: 제목 후보 {num_title_candidates}개 생성
"카카오 출신 개발자가 괴물같은 프로그램을 만들어 버렸습니다" 처럼 호기심을 자극하는 제목을 만드세요.

## 스크립트 구조 가이드 (개발남루씨 스타일)
- hook (5-10초): 결과물이나 충격적 사실 먼저 보여주기
- problem (10-15초): 기존의 문제점/불편함 제시
- introduction (10-20초): 솔루션 등장
- feature (각 15-25초): 핵심 기능 2-3개 (시각적 데모)
- closing (10-15초): 정리 + CTA

## 출력 형식 (JSON)
{{
    "title": "최종 선택된 제목",
    "title_candidates": [
        {{
            "title": "제목 후보 1",
            "style": "흥미유발",
            "reason": "이 제목이 좋은 이유",
            "score": 8.5
        }},
        {{
            "title": "제목 후보 2",
            "style": "정보전달",
            "reason": "이유",
            "score": 7.0
        }},
        {{
            "title": "제목 후보 3",
            "style": "감성",
            "reason": "이유",
            "score": 6.5
        }}
    ],
    "concept": "영상 컨셉 한 줄 설명",
    "target_viewer": "타겟 시청자 설명",
    "total_duration_sec": {target_duration},
    "scenes": [
        {{
            "scene_id": 1,
            "type": "hook",
            "duration_sec": 8,
            "narration": "나레이션 텍스트 (자연스러운 구어체)",
            "visual_direction": "화면 구성 지시",
            "text_overlay": "화면에 큰 글씨로 표시할 핵심 텍스트",
            "transition": "fade",
            "image_prompt": "이 씬에 필요한 이미지를 AI로 생성하기 위한 영문 프롬프트"
        }}
    ]
}}

JSON만 출력하세요."""

    try:
        content = _call_llm(prompt, max_tokens=4096)
        data = _parse_json(content)

        # Auto-select best title
        if auto_select and data.get("title_candidates"):
            best = max(data["title_candidates"], key=lambda x: x.get("score", 0))
            data["title"] = best["title"]

        return VideoScript(**data)
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Script generation failed: {e}")


def generate_trending_script(
    topic: str,
    research_text: str,
    video_type: str = "news",
    target_duration: int = 120,
    language: str = "ko",
) -> tuple[AnalysisReport, VideoScript]:
    """Generate analysis + script from trending topic research (no YouTube source)."""
    logger.info(f"Generating trending content script for: {topic}")

    prompt = f"""다음 트렌딩 주제에 대한 리서치 자료를 기반으로:
1. 콘텐츠 분석 보고서
2. {target_duration}초 길이의 영상 스크립트

두 가지를 한번에 생성하세요.

## 주제: {topic}

## 리서치 자료
{research_text[:8000]}

## 제목 스타일
"카카오 출신 개발자가 괴물같은 프로그램을 만들어 버렸습니다" 처럼 호기심 자극형

## 출력 형식 (JSON)
{{
    "analysis": {{
        "summary": "주제 전체 요약 (2-3문장)",
        "key_topics": ["주요 주제 1"],
        "product_features": [],
        "target_audience": "대상 시청자",
        "tone": "톤앤매너",
        "concept": "핵심 컨셉",
        "core_promise": "시청자가 얻는 가치",
        "emotion_strategy": "감정 전략",
        "segments": [
            {{"topic": "세그먼트 주제", "summary": "요약", "key_points": ["포인트"]}}
        ],
        "source_type": "trending"
    }},
    "script": {{
        "title": "최종 제목",
        "title_candidates": [
            {{"title": "후보1", "style": "흥미유발", "reason": "이유", "score": 8.5}},
            {{"title": "후보2", "style": "정보전달", "reason": "이유", "score": 7.0}},
            {{"title": "후보3", "style": "감성", "reason": "이유", "score": 6.5}}
        ],
        "concept": "영상 컨셉",
        "target_viewer": "타겟 시청자",
        "total_duration_sec": {target_duration},
        "scenes": [
            {{
                "scene_id": 1,
                "type": "hook",
                "duration_sec": 8,
                "narration": "나레이션",
                "visual_direction": "시각 연출",
                "text_overlay": null,
                "transition": "fade",
                "image_prompt": "영문 이미지 프롬프트"
            }}
        ]
    }}
}}

JSON만 출력하세요."""

    try:
        content = _call_llm(prompt, max_tokens=4096)
        data = _parse_json(content)

        # Auto-select best title
        script_data = data["script"]
        if script_data.get("title_candidates"):
            best = max(script_data["title_candidates"], key=lambda x: x.get("score", 0))
            script_data["title"] = best["title"]

        analysis = AnalysisReport(**data["analysis"])
        script = VideoScript(**script_data)
        return analysis, script
    except Exception as e:
        raise LLMError(f"Trending script generation failed: {e}")
