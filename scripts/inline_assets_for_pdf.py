#!/usr/bin/env python3
"""Inline local <img src="..."> assets into an HTML file as data: URIs.

Why:
- Headless Chromium in containers can be flaky with local file access across directories.
- Inlining makes the HTML self-contained and more deterministic for PDF rendering.

Usage:
  python scripts/inline_assets_for_pdf.py input.html output.html
"""

from __future__ import annotations

import base64
import mimetypes
import re
import sys
from pathlib import Path


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)("[^>]*?>)', re.IGNORECASE)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*?>[\s\S]*?</script>", re.IGNORECASE)


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        return mime

    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".svg":
        return "image/svg+xml"
    if ext == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _should_inline(src: str) -> bool:
    lowered = src.strip().lower()
    return not (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("data:")
        or lowered.startswith("//")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
    )


def inline_assets(input_html: Path, output_html: Path) -> None:
    html = input_html.read_text(encoding="utf-8")

    # Remove scripts to reduce chances of headless hangs.
    html = _SCRIPT_BLOCK_RE.sub("", html)

    base_dir = input_html.parent

    def repl(match: re.Match[str]) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)
        if not _should_inline(src):
            return match.group(0)

        # Drop querystrings/fragments for local file paths.
        src_path_part = src.split("#", 1)[0].split("?", 1)[0]
        candidate = (base_dir / src_path_part).resolve()

        if not candidate.exists() or not candidate.is_file():
            # Leave as-is if we cannot resolve the local asset.
            return match.group(0)

        mime = _guess_mime(candidate)
        data_b64 = base64.b64encode(candidate.read_bytes()).decode("ascii")
        data_uri = f"data:{mime};base64,{data_b64}"
        return f"{prefix}{data_uri}{suffix}"

    html = _IMG_SRC_RE.sub(repl, html)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python scripts/inline_assets_for_pdf.py input.html output.html", file=sys.stderr)
        return 2

    input_html = Path(argv[1]).resolve()
    output_html = Path(argv[2]).resolve()

    if not input_html.exists():
        print(f"[ERROR] Input HTML not found: {input_html}", file=sys.stderr)
        return 3

    inline_assets(input_html, output_html)
    print(f"Wrote self-contained HTML: {output_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
