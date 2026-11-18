#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Licensed under the Apache License, Version 2.0 (see LICENSE).
#
# =================================================================
"""
Authored content blocks for the generated Metanorma document.

A content block is a piece of author-supplied material that is carried into the
PDF alongside the generated sections. Four formats are supported:

* ``asciidoc``     - raw AsciiDoc passed through verbatim.
* ``markdown``     - converted to AsciiDoc (common subset, see
                     :func:`markdown_to_asciidoc`).
* ``preformatted`` - rendered as a monospace listing block, so line breaks and
                     spacing are preserved (ASCII art, console output,
                     fixed-width tables).
* ``plantuml``     - PlantUML source that Metanorma renders to an image.

This module has no dependency on the Pydantic models; blocks are duck-typed
(``format``, ``body``, ``title``, ``id``).
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

# Maximum AsciiDoc section level is 6 ('======').
_MAX_HEADING = 6

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

_MD = MarkdownIt("commonmark").enable(["table", "strikethrough"])


def _delimiter(body: str, char: str, minimum: int = 4) -> str:
    """Return a block delimiter of ``char`` that never appears alone on a line of body.

    AsciiDoc closes a delimited block at the first line equal to the opening
    delimiter, so a body containing e.g. '....' would otherwise be truncated.
    """
    lines = {line.strip() for line in body.splitlines()}
    n = minimum
    while char * n in lines:
        n += 1
    return char * n


# AsciiDoc preprocessor directives (include::, ifdef:: ...) are processed on
# every line, even inside listing blocks, so a line such as "include::x.adoc[]"
# in preformatted text would be executed (and abort the PDF if the file is
# missing). Metanorma runs the preprocessor twice, which consumes the usual
# backslash escape, so a zero-width space is inserted before the '::' instead.
# It prints as nothing in the PDF's monospace font (FiraCode has a zero-width
# glyph for U+200B) and only affects lines that start with a directive.
_DIRECTIVE_RE = re.compile(r"^(include|ifdef|ifndef|ifeval|endif)::", re.M)


def _verbatim(body: str) -> str:
    """Make a block body pass through AsciiDoc unprocessed."""
    return _DIRECTIVE_RE.sub("\\1\u200b::", body)


def _link_target(href: str) -> str:
    return href if _SCHEME_RE.match(href) else f"link:{href}"


def _inline(children) -> str:
    out: list[str] = []
    for tok in children or []:
        t = tok.type
        if t == "text":
            out.append(tok.content)
        elif t == "code_inline":
            # `+...+` keeps the content literal (no further AsciiDoc markup).
            out.append(f"`+{tok.content}+`")
        elif t in ("strong_open", "strong_close"):
            out.append("**")  # unconstrained: also works mid-word
        elif t in ("em_open", "em_close"):
            out.append("__")
        elif t == "s_open":
            out.append("[.line-through]#")
        elif t == "s_close":
            out.append("#")
        elif t == "softbreak":
            out.append("\n")
        elif t == "hardbreak":
            out.append(" +\n")
        elif t == "link_open":
            out.append(f"{_link_target(tok.attrGet('href') or '')}[")
        elif t == "link_close":
            out.append("]")
        elif t == "image":
            alt = tok.content or ""
            out.append(f"image:{tok.attrGet('src') or ''}[{alt}]")
        elif t in ("html_inline",):
            out.append(tok.content)
        elif tok.children:
            out.append(_inline(tok.children))
        else:
            out.append(tok.content)
    return "".join(out)


def markdown_to_asciidoc(md: str, heading_offset: int = 2, discrete: bool = False) -> str:
    """Convert Markdown to AsciiDoc (Metanorma flavour).

    Supported: headings, paragraphs, bold/italic/strikethrough, inline code,
    links, images, bullet and numbered lists (nested), fenced/indented code,
    block quotes, thematic breaks, GFM tables and raw HTML pass-through.

    Heading levels are relative to the shallowest heading in ``md``, and
    ``heading_offset`` is added to get the number of ``=`` signs. With the default
    of 2 the top-most Markdown heading (``#`` or ``##``) becomes a ``===``
    sub-heading of the enclosing ``==`` clause or annex.

    With ``discrete`` the headings are emitted as ``[discrete]`` (floating)
    headings: they look like headings but do not open a sub-clause, so content
    that follows them (e.g. the next requirement) is not pulled into it.
    """
    tokens = _MD.parse(md)
    # Levels are relative to the shallowest heading used, so a body that starts at
    # '##' still begins at the first sub-level instead of skipping one.
    levels = [int(t.tag[1:]) for t in tokens if t.type == "heading_open"]
    base = min(levels) if levels else 1
    out: list[str] = []
    list_stack: list[str] = []  # 'bullet' | 'ordered' per nesting level
    pending_marker: str | None = None
    table: dict | None = None

    def emit(text: str) -> None:
        out.append(text)

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        t = tok.type

        if t == "heading_open":
            level = int(tok.tag[1:]) - base + 1
            marks = "=" * min(level + heading_offset, _MAX_HEADING)
            if discrete:
                emit("[discrete]")
            emit(f"{marks} {_inline(tokens[i + 1].children)}\n")
            i += 3
            continue

        if t == "paragraph_open":
            text = _inline(tokens[i + 1].children)
            if table is not None:
                pass
            elif list_stack:
                if pending_marker is not None:
                    emit(f"{pending_marker}{text}")
                    pending_marker = None
                else:
                    emit(f"+\n{text}")
            else:
                emit(f"{text}\n")
            i += 3
            continue

        if t in ("bullet_list_open", "ordered_list_open"):
            list_stack.append("bullet" if t == "bullet_list_open" else "ordered")
        elif t in ("bullet_list_close", "ordered_list_close"):
            list_stack.pop()
            if not list_stack:
                emit("")  # blank line after the outermost list
        elif t == "list_item_open":
            ch = "*" if list_stack[-1] == "bullet" else "."
            pending_marker = f"{ch * len(list_stack)} "
        elif t in ("fence", "code_block"):
            lang = (tok.info or "").strip().split(" ")[0] if t == "fence" else ""
            body = _verbatim(tok.content.rstrip("\n"))
            delim = _delimiter(body, "-")
            if list_stack:
                emit("+")
            # subs=-callouts: a code line ending in '<1>' stays as written.
            if lang:
                emit(f'[source,{lang},subs="-callouts"]')
            else:
                emit('[source,subs="-callouts"]')
            emit(f"{delim}\n{body}\n{delim}\n")
        elif t == "blockquote_open":
            emit("[quote]\n____")
        elif t == "blockquote_close":
            emit("____\n")
        elif t == "hr":
            emit("'''\n")
        elif t == "html_block":
            emit(tok.content.rstrip("\n") + "\n")
        elif t == "table_open":
            table = {"header": [], "rows": [], "row": [], "in_head": False}
        elif t == "thead_open":
            table["in_head"] = True
        elif t == "thead_close":
            table["in_head"] = False
        elif t == "tr_open":
            table["row"] = []
        elif t == "tr_close":
            (table["header"] if table["in_head"] else table["rows"]).append(table["row"])
        elif t in ("th_open", "td_open"):
            cell = _inline(tokens[i + 1].children).replace("|", "\\|")
            table["row"].append(cell.replace("\n", " "))
            i += 3
            continue
        elif t == "table_close":
            has_header = bool(table["header"])
            if has_header:
                emit("[%header]")
            emit("|===")
            for row in table["header"] + table["rows"]:
                # All cells of a row on ONE line: AsciiDoc infers the column
                # count from the first line, so one-cell-per-line would make a
                # single-column table.
                emit(" ".join(f"| {c}" for c in row) + "\n")
            emit("|===\n")
            table = None

        i += 1

    # Collapse the runs of blank lines the emitters can leave behind.
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n") + "\n"


def _plantuml_source(body: str) -> str:
    """Wrap bare PlantUML in @startuml/@enduml (Metanorma requires them)."""
    stripped = body.strip()
    if "@start" in stripped:
        return stripped
    return f"@startuml\n{stripped}\n@enduml"


def render_text(body: str, fmt: str = "asciidoc", heading_offset: int = 2,
                discrete: bool = False) -> str:
    """Render a body string in ``fmt`` ('asciidoc' or 'markdown') to AsciiDoc."""
    if fmt == "markdown":
        return markdown_to_asciidoc(body, heading_offset, discrete).rstrip("\n")
    return body.rstrip()


def render_block(block, heading_offset: int = 2, discrete: bool = False) -> str:
    """Render one content block to AsciiDoc."""
    fmt = block.format
    lines: list[str] = []
    if getattr(block, "id", None):
        lines.append(f"[[{block.id}]]")

    if fmt in ("asciidoc", "markdown"):
        lines.append(render_text(block.body, fmt, heading_offset, discrete))
        return "\n".join(lines)

    if getattr(block, "title", None):
        lines.append(f".{block.title}")

    if fmt == "preformatted":
        # A listing block ('----'), not a literal ('....'): in the Metanorma OGC
        # PDF a titled literal becomes a figure whose text is reflowed onto one
        # line, while a listing keeps every line break and uses the monospace font.
        # Tabs are expanded to spaces (8-column stops, the terminal convention):
        # the PDF renders a raw tab as a single space, which breaks alignment.
        body = _verbatim(block.body.rstrip("\n").expandtabs(8))
        delim = _delimiter(body, "-")
        # subs=-callouts keeps a trailing '<1>' as text; special characters are
        # still escaped so < > & print as typed.
        lines += ['[subs="-callouts"]', delim, body, delim]
    elif fmt == "plantuml":
        body = _verbatim(_plantuml_source(block.body))
        delim = _delimiter(body, ".")
        lines += ["[plantuml]", delim, body, delim]
    else:  # pragma: no cover - guarded by the model's Literal type
        raise ValueError(f"unknown content block format: {fmt!r}")
    return "\n".join(lines)


def render_blocks(blocks, heading_offset: int = 2, discrete: bool = False) -> str:
    """Render a list of content blocks, separated by blank lines."""
    if not blocks:
        return ""
    return "\n\n".join(render_block(b, heading_offset, discrete) for b in blocks) + "\n"
