"""Scan files for user-defined vibe presets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from prodguardian.scan.presets_data import get_preset_keywords


def scan_file_presets(
    file_path: Path,
    content: str,
    presets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return issues when preset keywords/packages appear in a file."""
    issues: list[dict[str, Any]] = []
    enabled = [p for p in presets if p.get("enabled", True)]
    if not enabled or not content:
        return issues

    lines = content.splitlines()
    seen: set[tuple[str, int, str]] = set()

    for preset in enabled:
        preset_name = preset.get("name", "Custom preset")
        severity = str(preset.get("severity", "HIGH")).upper()
        category = preset.get("category", "")
        for item in get_preset_keywords(preset):
            item_lower = item.lower()
            for line_no, line in enumerate(lines, start=1):
                if item_lower not in line.lower():
                    continue
                key = (preset_name, line_no, item)
                if key in seen:
                    continue
                seen.add(key)
                cat_hint = f" ({category})" if category else ""
                issues.append(
                    {
                        "rule_id": "PRESET001",
                        "severity": severity,
                        "file": str(file_path),
                        "line": line_no,
                        "message": (
                            f"Vibe preset [{preset_name}]{cat_hint}: "
                            f"'{item}' must not ship to production"
                        ),
                        "code_snippet": line.strip()[:120],
                        "preset": preset_name,
                        "matched_item": item,
                        "category": category,
                    }
                )
    return issues


def scan_tree_presets(
    root: Path,
    presets: list[dict[str, Any]],
    should_ignore,
    on_progress: Callable[[str, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Scan all files under root using the preset matcher."""
    enabled = [p for p in presets if p.get("enabled", True)]
    paths = [
        path
        for path in root.rglob("*")
        if path.is_file() and not should_ignore(path)
    ]
    total = len(paths)
    all_issues: list[dict[str, Any]] = []

    if on_progress:
        on_progress(
            "presets",
            {
                "message": "Matching vibe preset keywords in source files",
                "preset_count": len(enabled),
                "files_total": total,
                "files_done": 0,
                "issues_found": 0,
            },
        )

    for done, path in enumerate(paths, start=1):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        found = scan_file_presets(path, content, presets)
        all_issues.extend(found)

        if on_progress:
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = str(path)
            on_progress(
                "presets",
                {
                    "message": f"Preset scan: {rel}",
                    "preset_count": len(enabled),
                    "files_total": total,
                    "files_done": done,
                    "current_file": rel,
                    "issues_found": len(all_issues),
                },
            )
    return all_issues