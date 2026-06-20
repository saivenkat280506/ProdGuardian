"""Copy text to the system clipboard (terminal + native fallbacks)."""

from __future__ import annotations

import platform
import subprocess
from typing import Callable


def strip_rich_markup(text: str) -> str:
    """Convert Rich markup strings to plain text for clipboard export."""
    try:
        from rich.text import Text

        return Text.from_markup(text).plain
    except Exception:
        return text


def _copy_windows(text: str) -> bool:
    try:
        subprocess.run(
            ["clip"],
            input=text,
            text=True,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _copy_macos(text: str) -> bool:
    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
        return True
    except Exception:
        return False


def _copy_linux(text: str) -> bool:
    for cmd in (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ):
        try:
            subprocess.run(cmd, input=text, text=True, check=True)
            return True
        except Exception:
            continue
    return False


def copy_to_system_clipboard(text: str) -> bool:
    """Best-effort clipboard write using the OS clipboard tool."""
    system = platform.system()
    if system == "Windows":
        return _copy_windows(text)
    if system == "Darwin":
        return _copy_macos(text)
    return _copy_linux(text)


def copy_report_text(
    text: str,
    *,
    terminal_copy: Callable[[str], None] | None = None,
) -> bool:
    """
    Copy report text to clipboard.

    Tries the native OS clipboard first, then optional terminal OSC-52 hook.
    """
    plain = strip_rich_markup(text)
    if copy_to_system_clipboard(plain):
        return True
    if terminal_copy is not None:
        try:
            terminal_copy(plain)
            return True
        except Exception:
            return False
    return False