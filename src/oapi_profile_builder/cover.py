# =================================================================
#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# =================================================================
"""
Custom PDF cover-page generation.

When a profile sets ``document_metadata.cover.logo``, the builder renders a
replacement cover-page image (organisation logo + the document's title, number,
edition and date) which Metanorma then uses in place of the built-in OGC cover
via ``:coverpage-image:`` + ``:presentation-metadata-full-coverpage-replacement:``.

Rendering uses Pillow. DejaVu fonts are bundled with Pillow and resolved by name,
so no system font paths are required.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

# A4 portrait at ~150 DPI.
_PAGE_W = 1240
_PAGE_H = 1754

_COVER_FILENAME = "cover.png"


def _load_font(bold: bool, size: int):
    from PIL import ImageFont

    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size)
    except Exception:
        # Last-resort fallback; not scalable but keeps rendering from failing.
        return ImageFont.load_default()


def _italic_font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.truetype("DejaVuSans-Oblique.ttf", size)
    except Exception:
        return _load_font(False, size)


def _format_date(iso_date: str | None) -> str | None:
    """Format 'YYYY-MM-DD' as 'DD Month YYYY' (e.g. '15 May 2026')."""
    if not iso_date:
        return None
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date
    # %-d is not portable; strip a leading zero manually.
    return f"{dt.day} {dt.strftime('%B %Y')}"


def build_cover_image(profile, output_dir: Path) -> str | None:
    """Render the cover PNG into output_dir. Returns its filename, or None.

    Returns None when no cover logo is configured. Raises RuntimeError with a
    clear message if Pillow is unavailable or the logo file cannot be found.
    """
    m = getattr(profile, "document_metadata", None)
    cover = getattr(m, "cover", None) if m else None
    if not cover or not cover.logo:
        return None

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depends on env
        raise RuntimeError(
            "document_metadata.cover.logo is set but Pillow is not installed. "
            "Install it with: pip install 'oapi-profile-builder[pdf]'"
        ) from exc

    logo_path = Path(cover.logo).expanduser()
    if not logo_path.is_absolute():
        logo_path = (Path.cwd() / logo_path).resolve()
    if not logo_path.exists():
        raise RuntimeError(f"Cover logo not found: {logo_path}")

    bg = cover.background or "#FFFFFF"
    fg = cover.text_color or "#000000"

    page = Image.new("RGB", (_PAGE_W, _PAGE_H), bg)
    draw = ImageDraw.Draw(page)

    def centered(text: str, font, y: int, fill: str) -> int:
        """Draw text horizontally centered; return the y below the text."""
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((_PAGE_W - tw) / 2, y), text, font=font, fill=fill)
        return y + th

    y = 180

    # --- Logo (centered, scaled to a target width) ---
    logo = Image.open(logo_path).convert("RGBA")
    target_logo_w = 420          # desired cover logo width
    max_logo_w = 520             # hard cap
    max_upscale = 3.0            # don't upscale tiny logos beyond this (avoids heavy blur)
    desired = min(target_logo_w, int(logo.width * max_upscale), max_logo_w)
    if logo.width != desired:
        scale = desired / logo.width
        logo = logo.resize((desired, max(1, int(logo.height * scale))))
    logo_x = int((_PAGE_W - logo.width) / 2)
    page.paste(logo, (logo_x, y), logo)
    y += logo.height + 60

    # --- Tagline (italic) ---
    if cover.tagline:
        y = centered(cover.tagline, _italic_font(30), y, fg) + 60

    # --- Document number ---
    if m and m.doc_number:
        y = centered(m.doc_number, _load_font(True, 46), y, fg) + 40

    # --- Edition ---
    edition = getattr(profile, "version", None)
    if edition:
        y = centered(f"Edition {edition}", _load_font(False, 28), y, fg) + 24

    # --- Date ---
    date_str = _format_date(m.publication_date if m else None)
    if date_str:
        y = centered(f"Dated {date_str}", _load_font(False, 28), y, fg) + 80

    # --- Title (large, bold, wrapped) ---
    title = getattr(profile, "title", "") or ""
    title_font = _load_font(True, 54)
    for line in _wrap(draw, title, title_font, _PAGE_W - 240):
        y = centered(line, title_font, y, fg) + 16

    target = (output_dir / _COVER_FILENAME).resolve()
    if not str(target).startswith(str(output_dir.resolve())):
        raise RuntimeError(f"Refusing to write cover outside output directory: {target}")
    page.save(target)
    return _COVER_FILENAME


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap to fit max_width pixels."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines
