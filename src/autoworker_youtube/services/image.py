"""Image generation service for text cards and overlays."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a Korean-supporting font."""
    # (path, index) - index is needed for .ttc collection files
    font_candidates = [
        # Nanum fonts (ttf - no index needed)
        ("/usr/share/fonts/truetype/nanum/NanumSquareB.ttf", 0),
        ("/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf", 0),
        ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
        # Noto CJK (ttc - KR is typically index 4)
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 4),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 4),
        # macOS
        ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
        # Windows
        ("C:/Windows/Fonts/malgun.ttf", 0),
        ("C:/Windows/Fonts/NanumGothic.ttf", 0),
        # Fallback
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ]
    # Also check project assets
    project_fonts = Path(__file__).parent.parent.parent.parent / "assets" / "fonts"
    if project_fonts.exists():
        for f in sorted(project_fonts.glob("*.ttf")):
            font_candidates.insert(0, (str(f), 0))
        for f in sorted(project_fonts.glob("*.ttc")):
            font_candidates.insert(0, (str(f), 0))

    for font_path, index in font_candidates:
        try:
            return ImageFont.truetype(font_path, size, index=index)
        except (OSError, IOError):
            continue

    logger.warning("No Korean font found! Text will be broken. Install: apt install fonts-nanum")
    return ImageFont.load_default()


def create_text_card(
    text: str,
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
    bg_color: str = "#1a1a2e",
    text_color: str = "#ffffff",
    font_size: int = 60,
    subtitle: str | None = None,
) -> Path:
    """Create a text card image with title and optional subtitle."""
    img = Image.new("RGB", resolution, bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)

    # Center the main text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Word wrap if text is too wide
    max_width = resolution[0] - 200
    if text_width > max_width:
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            test_bbox = draw.textbbox((0, 0), test_line, font=font)
            if test_bbox[2] - test_bbox[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        text = "\n".join(lines)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

    x = (resolution[0] - text_width) // 2
    y = (resolution[1] - text_height) // 2 - (40 if subtitle else 0)

    draw.text((x, y), text, fill=text_color, font=font)

    # Draw subtitle
    if subtitle:
        sub_font = _get_font(font_size // 2)
        sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        sub_x = (resolution[0] - sub_width) // 2
        sub_y = y + text_height + 40
        draw.text((sub_x, sub_y), subtitle, fill="#aaaaaa", font=sub_font)

    img.save(str(output_path), quality=95)
    logger.debug(f"Created text card: {output_path}")
    return output_path


def create_scene_images(
    scenes: list[dict],
    output_dir: Path,
    resolution: tuple[int, int] = (1920, 1080),
) -> list[Path]:
    """Create background images for each scene."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    # Color scheme for different scene types
    colors = {
        "hook": "#e94560",
        "introduction": "#0f3460",
        "feature": "#16213e",
        "demo": "#1a1a2e",
        "cta": "#e94560",
        "outro": "#0f3460",
    }

    for scene in scenes:
        scene_id = scene["scene_id"]
        scene_type = scene.get("type", "feature")
        text_overlay = scene.get("text_overlay") or scene.get("visual_direction", "")
        narration = scene.get("narration", "")

        bg_color = colors.get(scene_type, "#1a1a2e")

        # Use text overlay as main text, or first sentence of narration
        display_text = text_overlay
        if not display_text and narration:
            display_text = narration.split(".")[0].split("?")[0][:50]

        path = output_dir / f"scene_{scene_id:03d}.jpg"
        create_text_card(
            text=display_text or f"Scene {scene_id}",
            output_path=path,
            resolution=resolution,
            bg_color=bg_color,
            subtitle=scene_type.upper(),
        )
        paths.append(path)

    logger.info(f"Created {len(paths)} scene images")
    return paths
