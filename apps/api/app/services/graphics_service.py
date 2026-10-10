"""Original graphics (Phase 9 / D11): charts + timeline strips.

Pillow only - deterministic, no matplotlib, no fonts beyond the bundled
default. Used to produce original overlay art (charts, timeline strip) that
is composited into episodes by the renderer, which is what turns a
compilation into editorial production.
"""

import structlog
from pathlib import Path

log = structlog.get_logger()

BG = (16, 16, 30)
FG = (255, 255, 255)
ACCENT = (70, 130, 220, 255)
MUTED = (150, 150, 170, 255)


def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _canvas(w: int, h: int):
    from PIL import Image

    return Image.new("RGB", (w, h), BG)


def _fit(text: str, font, max_w: int) -> str:
    from PIL import ImageDraw

    probe = ImageDraw.Draw(_canvas(8, 8))
    while text and probe.textlength(text, font=font) > max_w:
        text = text[:-1]
    return text.rstrip() + ("…" if text else "")


def bar_chart(png_path: Path, data: list[tuple[str, int]], title: str = "",
              width: int = 1280, height: int = 720) -> Path:
    """Vertical bar chart with value labels."""
    from PIL import ImageDraw

    img = _canvas(width, height)
    draw = ImageDraw.Draw(img)
    title_font = _font(44)
    label_font = _font(30)
    value_font = _font(28)

    if title:
        draw.text((60, 48), _fit(title, title_font, width - 120),
                  font=title_font, fill=FG)
    data = data[:8] or [("none", 0)]
    top, bottom = 150, height - 130
    slot = (width - 160) / len(data)
    peak = max(v for _, v in data) or 1
    bar_w = max(int(slot * 0.55), 24)
    for i, (label, value) in enumerate(data):
        x = 80 + i * slot + (slot - bar_w) / 2
        h = (value / peak) * (bottom - top)
        draw.rectangle([x, bottom - h, x + bar_w, bottom], fill=ACCENT)
        draw.text((x, bottom - h - 38), f"{value:,}", font=value_font,
                  fill=FG)
        draw.text((x, bottom + 18), _fit(label, label_font, int(slot)),
                  font=label_font, fill=MUTED)
    draw.line([80, bottom, width - 80, bottom], fill=MUTED, width=2)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path)
    log.info("chart_rendered", path=str(png_path), bars=len(data))
    return png_path


def timeline_strip(png_path: Path,
                   segments: list[tuple[str, float]],
                   width: int = 1280, height: int = 240) -> Path:
    """Horizontal proportional strip of the episode's segments."""
    from PIL import ImageDraw

    img = _canvas(width, height)
    draw = ImageDraw.Draw(img)
    palette = [(70, 130, 220, 255), (70, 200, 150, 255), (230, 150, 60, 255),
               (200, 80, 140, 255), (140, 120, 230, 255), (90, 190, 200, 255)]
    total = sum(max(d, 0.0) for _, d in segments) or 1.0
    font = _font(28)
    x = 40
    bar_h = 96
    for i, (label, duration) in enumerate(segments[:12]):
        w = int((max(duration, 0.0) / total) * (width - 80))
        color = palette[i % len(palette)]
        draw.rectangle([x, 70, x + max(w, 2), 70 + bar_h], fill=color)
        shown = _fit(label, font, max(w - 16, 60))
        draw.text((x + 8, 70 + bar_h // 2 - 16), shown, font=font, fill=(0, 0, 0))
        x += w
    draw.text((40, 190), "Episode timeline", font=_font(34), fill=FG)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path)
    log.info("timeline_rendered", path=str(png_path), segments=len(segments))
    return png_path
