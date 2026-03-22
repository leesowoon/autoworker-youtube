"""AI image & video generation services.

Supports:
  - OpenAI DALL-E 3
  - Stability AI (Stable Diffusion)
  - xAI Grok (image + video)
  - Google Whisk (unofficial, browser-based fallback)
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from loguru import logger

from autoworker_youtube.core.config import settings as app_settings


# ---------------------------------------------------------------------------
# OpenAI DALL-E 3
# ---------------------------------------------------------------------------

def generate_gpt_image(
    prompt: str,
    output_path: Path,
    size: str = "1536x1024",
    quality: str = "medium",
    api_key: str | None = None,
) -> Path | None:
    """Generate an image using OpenAI GPT Image 1.5.

    The latest OpenAI image model (replaces DALL-E 3).
    Supports up to 4096x4096, accurate text rendering, diverse styles.

    Requires: pip install openai
    Env: OPENAI_API_KEY

    Quality options: low ($0.02), medium ($0.07), high ($0.19) per image.
    Size options: 1024x1024, 1536x1024, 1024x1536, auto.
    """
    api_key = api_key or app_settings.openai_api_key
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, skipping GPT Image generation")
        return None

    try:
        import base64

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )

        # GPT Image returns base64 JSON (no URL)
        image_data = response.data[0].b64_json
        if image_data:
            image_bytes = base64.b64decode(image_data)
            output_path.write_bytes(image_bytes)
            logger.info(f"GPT Image 1.5 saved: {output_path}")
            return output_path
        else:
            # Fallback: try URL if available
            image_url = getattr(response.data[0], "url", None)
            if image_url:
                import requests
                dl = requests.get(image_url, timeout=30)
                if dl.status_code == 200:
                    output_path.write_bytes(dl.content)
                    logger.info(f"GPT Image 1.5 saved (url): {output_path}")
                    return output_path
            logger.error("GPT Image: no image data in response")
            return None
    except Exception as e:
        logger.error(f"GPT Image generation failed: {e}")
        return None


# Keep dalle as alias for backward compatibility
generate_dalle = generate_gpt_image


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
    api_key = api_key or app_settings.stability_api_key
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
    api_key = api_key or app_settings.xai_api_key
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
                "model": "grok-imagine-image",
                "prompt": prompt,
                "n": 1,
                "response_format": "url",
            },
            timeout=60,
        )

        if response.status_code == 200:
            data = response.json()
            image_url = data["data"][0]["url"]
            # Download with requests (urllib gets 403 on xAI URLs)
            img_resp = requests.get(image_url, timeout=30)
            if img_resp.status_code == 200:
                output_path.write_bytes(img_resp.content)
                logger.info(f"Grok image saved: {output_path}")
                return output_path
            else:
                logger.error(f"Grok image download failed: {img_resp.status_code}")
                return None
        else:
            logger.error(f"Grok image error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Grok image generation failed: {e}")
        return None


def _poll_grok_video(request_id: str, output_path: Path, api_key: str, max_wait: int) -> Path | None:
    """Poll for Grok video completion and download result."""
    import requests

    logger.info(f"Grok video generating (id={request_id}), polling...")

    # Try both endpoint patterns
    endpoints = [
        f"https://api.x.ai/v1/videos/{request_id}",
        f"https://api.x.ai/v1/videos/generations/{request_id}",
    ]

    for attempt in range(max_wait // 3):
        time.sleep(3)
        for endpoint in endpoints:
            try:
                status_resp = requests.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=15,
                )
            except Exception:
                continue

            if status_resp.status_code != 200:
                continue

            status_data = status_resp.json()
            state = status_data.get("status", status_data.get("state", ""))

            if attempt % 10 == 0:
                logger.info(f"  Video poll: status={state} ({(attempt+1)*3}s elapsed)")

            # Check for completion: "done", "completed", "succeeded"
            if state in ("done", "completed", "succeeded"):
                # Try multiple response formats
                video_url = ""
                # Format 1: {"video": {"url": "..."}}
                video_obj = status_data.get("video", {})
                if isinstance(video_obj, dict):
                    video_url = video_obj.get("url", "")
                # Format 2: {"video_url": "..."}
                if not video_url:
                    video_url = status_data.get("video_url", "")
                # Format 3: {"url": "..."}
                if not video_url:
                    video_url = status_data.get("url", "")
                # Format 4: {"data": [{"url": "..."}]}
                if not video_url:
                    results = status_data.get("data", status_data.get("results", []))
                    if results and isinstance(results, list):
                        video_url = results[0].get("url", "")

                if video_url:
                    dl = requests.get(video_url, timeout=120)
                    if dl.status_code == 200:
                        output_path.write_bytes(dl.content)
                        logger.info(f"Grok video saved: {output_path} ({len(dl.content)//1024}KB)")
                        return output_path
                    else:
                        logger.error(f"Video download failed: {dl.status_code}")
                else:
                    logger.error(f"Video done but no URL found in: {list(status_data.keys())}")
                return None

            elif state in ("failed", "error", "expired"):
                logger.error(f"Grok video failed: {status_data}")
                return None

            # Found a valid response from this endpoint, no need to try the other
            break

    logger.warning(f"Grok video timed out after {max_wait}s")
    return None


def generate_grok_video(
    prompt: str,
    output_path: Path,
    duration: int = 5,
    api_key: str | None = None,
    max_wait: int = 600,
) -> Path | None:
    """Generate a video from text prompt using xAI Grok Imagine Video."""
    api_key = api_key or app_settings.xai_api_key
    if not api_key:
        logger.warning("XAI_API_KEY not set, skipping Grok video generation")
        return None

    try:
        import requests

        response = requests.post(
            "https://api.x.ai/v1/videos/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-imagine-video",
                "prompt": prompt,
                "duration": duration,
            },
            timeout=30,
        )

        if response.status_code not in (200, 201, 202):
            logger.error(f"Grok video submit error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        request_id = data.get("id") or data.get("request_id", "")

        if not request_id:
            video_url = data.get("data", [{}])[0].get("url", "")
            if video_url:
                dl = requests.get(video_url, timeout=60)
                if dl.status_code == 200:
                    output_path.write_bytes(dl.content)
                    logger.info(f"Grok video saved: {output_path}")
                    return output_path
            return None

        return _poll_grok_video(request_id, output_path, api_key, max_wait)
    except Exception as e:
        logger.error(f"Grok video generation failed: {e}")
        return None


def generate_grok_image_to_video(
    image_path: Path,
    prompt: str,
    output_path: Path,
    duration: int = 5,
    api_key: str | None = None,
    max_wait: int = 600,
) -> Path | None:
    """Animate a still image into video using xAI Grok Image-to-Video.

    Takes an existing image and makes the content move/animate based on the prompt.
    E.g., a person in the image will start moving, backgrounds animate, etc.

    Args:
        image_path: Path to the source image to animate.
        prompt: Instructions for how to animate (e.g., "the person turns and walks away").
        output_path: Where to save the generated video.
        duration: Video duration in seconds (1-15).
        api_key: xAI API key.
        max_wait: Max seconds to wait for generation.
    """
    api_key = api_key or app_settings.xai_api_key
    if not api_key:
        logger.warning("XAI_API_KEY not set, skipping Grok image-to-video")
        return None

    if not image_path.exists():
        logger.error(f"Source image not found: {image_path}")
        return None

    try:
        import base64
        import io

        import requests
        from PIL import Image

        # Resize and compress image for faster processing
        img = Image.open(image_path)
        # Resize to max 1024px wide (keeps aspect ratio)
        max_w = 1024
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

        # Compress to JPEG ~200KB
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=75, optimize=True)
        image_bytes = buf.getvalue()
        mime = "image/jpeg"

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_data_uri = f"data:{mime};base64,{image_b64}"

        logger.info(f"Submitting image-to-video: {image_path.name} (compressed {len(image_bytes)//1024}KB)")

        response = requests.post(
            "https://api.x.ai/v1/videos/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-imagine-video",
                "prompt": prompt,
                "image_url": image_data_uri,
                "duration": duration,
            },
            timeout=60,
        )

        if response.status_code not in (200, 201, 202):
            logger.error(f"Grok image-to-video submit error {response.status_code}: {response.text[:300]}")
            return None

        data = response.json()
        request_id = data.get("id") or data.get("request_id", "")

        if not request_id:
            video_url = data.get("data", [{}])[0].get("url", "")
            if video_url:
                dl = requests.get(video_url, timeout=60)
                if dl.status_code == 200:
                    output_path.write_bytes(dl.content)
                    logger.info(f"Grok image-to-video saved: {output_path}")
                    return output_path
            return None

        return _poll_grok_video(request_id, output_path, api_key, max_wait)
    except Exception as e:
        logger.error(f"Grok image-to-video failed: {e}")
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
IMAGE_PROVIDERS = ["gpt_image", "grok", "stability", "whisk"]


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
        provider: Preferred provider (gpt_image, grok, stability, whisk, dalle).
                  If None, tries all in priority order.
        fallback: If True, try next provider on failure.

    Returns:
        Path to the generated image, or None if all providers fail.
    """
    providers = {
        "gpt_image": generate_gpt_image,
        "dalle": generate_dalle,  # alias for gpt_image
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
