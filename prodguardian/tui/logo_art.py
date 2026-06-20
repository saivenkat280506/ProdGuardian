"""ProdGuardian banner text — width-aligned for terminal rendering."""

from __future__ import annotations

from pathlib import Path

LOGO_PATH = Path(__file__).parent / "logo.txt"
FULL_WIDTH = 76


def _normalize_line(line: str, width: int = FULL_WIDTH) -> str:
    stripped = line.rstrip()
    if not stripped:
        return ""
    if "Production Readiness" in stripped:
        return stripped.center(width)
    if len(stripped) >= width:
        return stripped[:width]
    if set(stripped) <= {"_"}:
        return stripped.ljust(width, "_")
    if set(stripped) <= {"=", "\u2550"}:
        return "\u2550" * width
    return stripped.ljust(width)


def _load_full_logo() -> str:
    raw = LOGO_PATH.read_text(encoding="utf-8").splitlines()
    return "\n".join(_normalize_line(line) for line in raw)


def _compact_logo(width: int) -> str:
    inner = max(40, min(width - 4, 68))
    bar = "\u2550" * inner
    title = "ProdGuardian".center(inner)
    tagline = "Production Readiness & Security Auditor".center(inner)
    return f"{bar}\n{title}\n{tagline}\n{bar}"


def logo_for_terminal(width: int, height: int, layout_mode: str = "") -> str:
    """
    Pick a banner that fits the terminal without clipping.

    Prefer the full block-letter art whenever the terminal is wide enough.
    Only fall back to the compact banner on very narrow terminals.
    """
    if width < 64:
        return _compact_logo(width)

    if layout_mode == "layout-compact" and width < 72:
        return _compact_logo(width)

    if height < 18:
        return _compact_logo(width)

    return _load_full_logo()


def logo_line_count(text: str) -> int:
    """Return rendered line count (at least 1)."""
    lines = text.splitlines()
    return max(1, len(lines))


FULL_LOGO = _load_full_logo()