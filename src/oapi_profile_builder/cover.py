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

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# A4 portrait at ~150 DPI.
_PAGE_W = 1240
_PAGE_H = 1754

_COVER_FILENAME = "cover.png"

# Default font family (bundled with Pillow, resolved by name).
_DEFAULT_REGULAR = "DejaVuSans"
_DEFAULT_BOLD = "DejaVuSans-Bold"
_DEFAULT_ITALIC = "DejaVuSans:style=Oblique"


def _resolve_font_file(spec: str | None, *, bold: bool = False, italic: bool = False) -> str | None:
    """Resolve a user font spec to a usable font file path.

    ``spec`` may be either a path to a ``.ttf``/``.otf`` file or a font family
    name (e.g. ``"Source Sans Pro"``). Family names are resolved via
    ``fc-match`` (fontconfig) when available. Returns ``None`` when the spec is
    empty or cannot be resolved, so the caller can fall back to a default.
    """
    if not spec:
        return None
    p = Path(spec).expanduser()
    if p.is_file():
        return str(p)
    if shutil.which("fc-match"):
        # If the spec already contains a colon, treat it as a full fontconfig query
        if ":" in spec:
            query = spec
        else:
            styles = []
            if bold:
                styles.append("Bold")
            if italic:
                styles.append("Italic")
            query = spec if not styles else f"{spec}:style={' '.join(styles)}"
            
        try:
            # Try the primary query
            out = subprocess.run(
                ["fc-match", "-f", "%{file}", query],
                capture_output=True, text=True, timeout=5, check=False,
            )
            path = out.stdout.strip()
            if path and Path(path).is_file():
                # Verify that the result matches the requested style if possible.
                # If we asked for Italic but got a Regular file, fc-match just fell back.
                if italic and "Italic" not in path and "Oblique" not in path:
                    # Try a second attempt explicitly asking for Oblique if Italic failed
                    if ":" not in spec:
                        query_oblique = f"{spec}:style=Oblique"
                        out = subprocess.run(
                            ["fc-match", "-f", "%{file}", query_oblique],
                            capture_output=True, text=True, timeout=5, check=False,
                        )
                        path = out.stdout.strip()
                        if path and Path(path).is_file() and ("Italic" in path or "Oblique" in path):
                            return path
                else:
                    return path
        except Exception:
            pass
    return None


class _FontSet:
    """Resolves cover fonts from optional profile config, with sane defaults.

    Each of ``regular``/``bold``/``italic`` may be a font-file path or a family
    name; unset styles are derived from ``regular`` (with the matching style) and
    ultimately fall back to the bundled DejaVu family.
    """

    def __init__(self, cover=None, metadata=None):
        self.regular = getattr(cover, "font_regular", None) if cover else None
        self.bold = getattr(cover, "font_bold", None) if cover else None
        self.italic = getattr(cover, "font_italic", None) if cover else None
        
        # Fallback to metadata-level font overrides if set
        if not self.regular and metadata:
            self.regular = getattr(metadata, "body_font", None)
        if not self.bold and metadata:
            self.bold = getattr(metadata, "header_font", None)

    def _font(self, size: int, *, bold: bool = False, italic: bool = False):
        from PIL import ImageFont

        candidates = []
        # 1. Try explicit style override (path or family name)
        style_spec = self.bold if bold else (self.italic if italic else None)
        if style_spec:
            candidates.append(_resolve_font_file(style_spec, bold=bold, italic=italic))

        # 2. Try deriving from the regular spec if it is a family name
        if (bold or italic) and self.regular and not Path(self.regular).expanduser().is_file():
            candidates.append(_resolve_font_file(self.regular, bold=bold, italic=italic))

        # 3. Try standard defaults for the requested style
        candidates.append(_DEFAULT_BOLD if bold else (_DEFAULT_ITALIC if italic else _DEFAULT_REGULAR))

        # 4. Fallback to the regular font spec (even if not the right style)
        candidates.append(_resolve_font_file(self.regular))

        for cand in candidates:
            if not cand:
                continue
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def regular_font(self, size: int, bold: bool = False):
        return self._font(size, bold=bold)

    def italic_font(self, size: int):
        return self._font(size, italic=True)


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
    fonts = _FontSet(cover, m)

    page = Image.new("RGB", (_PAGE_W, _PAGE_H), bg)
    draw = ImageDraw.Draw(page)

    def centered(text: str, font, y: int, fill: str) -> int:
        """Draw text horizontally centered; return the y below the text."""
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((_PAGE_W - tw) / 2, y), text, font=font, fill=fill)
        return y + th

    y = getattr(cover, "logo_y", 180)

    # --- Logo (centered, scaled to a target width) ---
    logo = Image.open(logo_path).convert("RGBA")
    target_logo_w = getattr(cover, "logo_width", 420)
    max_logo_w = max(520, target_logo_w)
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
        tagline_fs = getattr(cover, "tagline_font_size", 30)
        tagline_font = fonts.italic_font(tagline_fs)
        for line in _wrap(draw, cover.tagline, tagline_font, _PAGE_W - 240):
            y = centered(line, tagline_font, y, fg) + 10
        y += 50

    # --- Document number ---
    if m and m.doc_number:
        doc_num_font = fonts.regular_font(46, bold=True)
        for line in _wrap(draw, m.doc_number, doc_num_font, _PAGE_W - 240):
            y = centered(line, doc_num_font, y, fg) + 16
        y += 24


    # --- Edition & date ---
    # Per DGIWG feedback these two lines are both bold and set a little smaller
    # than the document number so they read as a compact sub-heading.
    ed_date_fs = getattr(cover, "edition_date_font_size", 24)
    bold_ed = bool(getattr(cover, "bold_edition", False))

    edition = getattr(profile, "version", None)
    if edition:
        y = centered(f"Edition {edition}", fonts.regular_font(ed_date_fs, bold=bold_ed), y, fg) + 20

    pub_date = (m.doc_pub_date or m.publication_date) if m else None
    date_str = _format_date(pub_date)
    if date_str:
        y = centered(f"Dated {date_str}", fonts.regular_font(ed_date_fs, bold=bold_ed), y, fg) + 80

    # --- Title (large, bold, wrapped) ---
    title = getattr(profile, "title", "") or ""
    title_fs = getattr(cover, "title_font_size", 54)
    title_font = fonts.regular_font(title_fs, bold=True)
    for line in _wrap(draw, title, title_font, _PAGE_W - 240):
        y = centered(line, title_font, y, fg) + 16

    # --- Draft watermark (diagonal, semi-transparent) ---
    if getattr(cover, "watermark", None):
        _stamp_watermark(page, cover.watermark, fonts)

    target = (output_dir / _COVER_FILENAME).resolve()
    if not str(target).startswith(str(output_dir.resolve())):
        raise RuntimeError(f"Refusing to write cover outside output directory: {target}")
    page.save(target)
    return _COVER_FILENAME


def _stamp_watermark(page, text: str, fonts: "_FontSet") -> None:
    """Overlay a large, diagonal, semi-transparent watermark on the cover.

    Rendered on its own RGBA layer and rotated 45°, then alpha-composited onto
    the (RGB) cover page. Gives a clear 'DRAFT' style indication on the cover;
    an every-page watermark additionally requires the Metanorma layer.
    """
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", page.size, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layer)
    font = fonts.regular_font(150, bold=True)
    bbox = ldraw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ldraw.text(
        ((page.width - tw) / 2, (page.height - th) / 2),
        text, font=font, fill=(200, 0, 0, 70),
    )
    layer = layer.rotate(45, resample=Image.BICUBIC, center=(page.width / 2, page.height / 2))
    page.paste(Image.alpha_composite(page.convert("RGBA"), layer).convert("RGB"), (0, 0))


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
