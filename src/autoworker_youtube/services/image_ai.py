"""AI image & video generation services.

Supports:
  - OpenAI DALL-E 3
  - Stability AI (Stable Diffusion)
  - xAI Grok (image + video)
  - Google Whisk (unofficial, browser-based fallback)
"""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

from loguru import logger


# ---------------------------------------------------------------------------
# OpenAI DALL-E 3
# ---------------------------------------------------------------------------

def generate_dalle(
    prompt: str,
    output_path: Path,
    size: str = "1792x1024",
    quality: str = "standard",
    api_key: str | None = None,
) -> Path | None:
    """Generate an image using OpenAI DALL-E 3.

    Requires: pip install openai
    Env: OPENAI_API_KEY
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, skipping DALL-E generation")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        image_url = response.data[0].url

        # Download image
        urllib.request.urlretrieve(image_url, str(output_path))
        logger.info(f"DALL-E image saved: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"DALL-E generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Stability AI (Stable Diffusion)
# ---------------------------------------------------------------------------

def generate_stability(
    prompt: str,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    api_key: str | None = None,
) -> Path | None:
    """Generate an image using Stability AI API.

    Requires: requests
    Env: STABILITY_API_KEY
    """
    api_key = api_key or os.getenv("STABILITY_API_KEY", "")
    if not api_key:
        logger.warning("STABILITY_API_KEY not set, skipping Stability generation")
        return None

    try:
        import requests

        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/ultra",
            headers={
                "authorization": api_key,
                "accept": "image/*",
            },
            files={"none": ""},
            data={
                "prompt": prompt,
                "output_format": "jpeg",
                "aspect_ratio": "16:9",
            },
            timeout=60,
        )

        if response.status_code == 200:
            output_path.write_bytes(response.content)
            logger.info(f"Stability AI image saved: {output_path}")
            return output_path
        else:
            logger.error(f"Stability AI error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Stability AI generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# xAI Grok (Image + Video)
# ---------------------------------------------------------------------------

def generate_grok_image(
    prompt: str,
    output_path: Path,
    api_key: str | None = None,
) -> Path | None:
    """Generate an image using xAI Grok Imagine.

    Env: XAI_API_KEY
    """
    api_key = api_key or os.getenv("XAI_API_KEY", "")
    if not api_key:
        logger.warning("XAI_API_KEY not set, skipping Grok image generation")
        return None

    try:
        import requests

        response = requests.post(
            "https://api.x.ai/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-2-image",
                "prompt": prompt,
                "n": 1,
                "response_format": "url",
            },
            timeout=60,
        )

        if response.status_code == 200:
            data = response.json()
            image_url = data["data"][0]["url"]
            urllib.request.urlretrieve(image_url, str(output_path))
            logger.info(f"Grok image saved: {output_path}")
            return output_path
        else:
            logger.error(f"Grok image error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Grok image generation failed: {e}")
        return None


def generate_grok_video(
    prompt: str,
    output_path: Path,
    duration: int = 5,
    api_key: str | None = None,
    max_wait: int = 120,
) -> Path | None:
    """Generate a video using xAI Grok Imagine Video.

    Env: XAI_API_KEY
    """
    api_key = api_key or os.getenv("XAI_API_KEY", "")
    if not api_key:
        logger.warning("XAI_API_KEY not set, skipping Grok video generation")
        return None

    try:
        import requests

        # Step 1: Submit generation request
        response = requests.post(
            "https://api.x.ai/v1/videos/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-2-video",
                "prompt": prompt,
                "duration": duration,
            },
            timeout=30,
        )

        if response.status_code not in (200, 201, 202):
            logger.error(f"Grok video submit error: {response.status_code}")
            return None

        data = response.json()
        request_id = data.get("id") or data.get("request_id", "")

        if not request_id:
            # Direct response with URL
            video_url = data.get("data", [{}])[0].get("url", "")
            if video_url:
                urllib.request.urlretrieve(video_url, str(output_path))
                logger.info(f"Grok video saved: {output_path}")
                return output_path
            return None

        # Step 2: Poll for completion
        logger.info(f"Grok video generating (id={request_id}), polling...")
        for _ in range(max_wait // 5):
            time.sleep(5)
            status_resp = requests.get(
                f"https://api.x.ai/v1/videos/generations/{request_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if status_resp.status_code != 200:
                continue

            status_data = status_resp.json()
            state = status_data.get("state", status_data.get("status", ""))

            if state in ("completed", "succeeded"):
                video_url = status_data.get("video_url") or status_data.get("url", "")
                if not video_url:
                    results = status_data.get("data", status_data.get("results", []))
                    if results:
                        video_url = results[0].get("url", "")
                if video_url:
                    urllib.request.urlretrieve(video_url, str(output_path))
                    logger.info(f"Grok video saved: {output_path}")
                    return output_path
                return None
            elif state in ("failed", "error"):
                logger.error(f"Grok video generation failed: {status_data}")
                return None

        logger.warning("Grok video generation timed out")
        return None
    except Exception as e:
        logger.error(f"Grok video generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Google Whisk (unofficial - via browser automation or direct flow URL)
# ---------------------------------------------------------------------------

def generate_whisk(
    prompt: str,
    output_path: Path,
    style_image_path: Path | None = None,
) -> Path | None:
    """Generate image via Google Whisk/Flow.

    NOTE: Google Whisk has no official API. This is a placeholder that
    logs the prompt for manual use at https://labs.google.com/fx/tools/whisk
    or the merged Google Flow at https://flow.google

    For automated use, consider using the unofficial npm package
    @rohitaryal/whisk-api via subprocess, or use DALL-E/Stability as fallback.
    """
    logger.warning(
        "Google Whisk has no official API. "
        "Use https://flow.google manually or set up the unofficial whisk-api."
    )
    logger.info(f"Whisk prompt for manual use: {prompt}")

    # Try unofficial whisk-api if available (npm package)
    try:
        import subprocess

        result = subprocess.run(
            ["npx", "--yes", "@rohitaryal/whisk-api", "--prompt", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse output URL and download
            url = result.stdout.strip().split("\n")[-1]
            if url.startswith("http"):
                urllib.request.urlretrieve(url, str(output_path))
                logger.info(f"Whisk image saved: {output_path}")
                return output_path
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------

# Priority order for image generation
IMAGE_PROVIDERS = ["dalle", "grok", "stability", "whisk"]


def generate_image(
    prompt: str,
    output_path: Path,
    provider: str | None = None,
    fallback: bool = True,
) -> Path | None:
    """Generate an image using the specified provider, with fallback chain.

    Args:
        prompt: Image generation prompt (English recommended).
        output_path: Where to save the generated image.
        provider: Preferred provider (dalle, stability, grok, whisk).
                  If None, tries all in priority order.
        fallback: If True, try next provider on failure.

    Returns:
        Path to the generated image, or None if all providers fail.
    """
    providers = {
        "dalle": generate_dalle,
        "stability": generate_stability,
        "grok": generate_grok_image,
        "whisk": generate_whisk,
    }

    if provider:
        order = [provider] + [p for p in IMAGE_PROVIDERS if p != provider] if fallback else [provider]
    else:
        order = IMAGE_PROVIDERS

    for name in order:
        func = providers.get(name)
        if not func:
            continue
        logger.info(f"Trying image generation with {name}...")
        result = func(prompt=prompt, output_path=output_path)
        if result and result.exists():
            return result
        if not fallback:
            break

    logger.warning(f"All image providers failed for prompt: {prompt[:80]}...")
    return None


def generate_scene_images_ai(
    scenes: list[dict],
    output_dir: Path,
    provider: str | None = None,
    fallback: bool = True,
) -> list[Path | None]:
    """Generate AI images for all scenes.

    Falls back to text card for scenes where AI generation fails.
    """
    from autoworker_youtube.services.image import create_text_card

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for scene in scenes:
        scene_id = scene["scene_id"]
        image_prompt = scene.get("image_prompt", "")
        output_path = output_dir / f"scene_ai_{scene_id:03d}.jpg"

        if image_prompt:
            result = generate_image(
                prompt=image_prompt,
                output_path=output_path,
                provider=provider,
                fallback=fallback,
            )
            if result:
                results.append(result)
                continue

        # Fallback to text card
        text = scene.get("text_overlay") or scene.get("narration", "")[:50]
        fallback_path = output_dir / f"scene_{scene_id:03d}.jpg"
        create_text_card(
            text=text or f"Scene {scene_id}",
            output_path=fallback_path,
            subtitle=scene.get("type", "").upper(),
        )
        results.append(fallback_path)

    logger.info(f"Generated {len(results)} scene images (AI + fallback)")
    return results


def generate_video(
    prompt: str,
    output_path: Path,
    duration: int = 5,
    provider: str = "grok",
) -> Path | None:
    """Generate a video clip. Currently only xAI Grok supports this.

    Args:
        prompt: Video generation prompt.
        output_path: Where to save the video.
        duration: Duration in seconds (max ~15 for Grok).
        provider: Only 'grok' is currently supported.

    Returns:
        Path to the generated video, or None.
    """
    if provider == "grok":
        return generate_grok_video(prompt, output_path, duration)
    else:
        logger.warning(f"Video generation not supported for provider: {provider}")
        return None
