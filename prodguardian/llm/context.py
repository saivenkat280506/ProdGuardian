from pathlib import Path
from typing import Any

from prodguardian.scan.presets_data import build_llm_presets_context


def extract_context(issue: dict[str, Any], surrounding_lines: int = 20) -> str:
    """Extract code context around the issue line."""
    file_path = Path(issue["file"])
    if not file_path.exists():
        return ""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    line_no = issue.get("line", 0)
    if line_no <= 0:
        return ""
    start = max(0, line_no - surrounding_lines - 1)
    end = min(len(lines), line_no + surrounding_lines)
    context_lines = lines[start:end]
    marker_idx = line_no - start - 1
    if 0 <= marker_idx < len(context_lines):
        context_lines[marker_idx] = f">>> {context_lines[marker_idx]}"
    return "\n".join(context_lines)


def build_presets_context(
    presets: list[dict],
    rules: list[dict],
    *,
    compact: bool = False,
) -> str:
    """Build the presets + rules block injected into every LLM scan/fix prompt."""
    return build_llm_presets_context(presets, rules, compact=compact)


def build_prompt(
    issue: dict[str, Any],
    context: str,
    presets: list[dict] | None = None,
    rules: list[dict] | None = None,
) -> str:
    """Create a prompt for the LLM to explain or fix the issue."""
    guardrails = build_presets_context(presets or [], rules or [])
    guardrails_block = f"\n{guardrails}\n" if guardrails else ""

    prompt = f"""You are a security and production readiness expert.
{guardrails_block}
Issue: {issue.get('message', 'unknown')} (Rule: {issue.get('rule_id', 'unknown')}, Severity: {issue.get('severity', 'unknown')})
File: {issue.get('file', 'unknown')}, Line: {issue.get('line', 0)}

Code context (">>>" marks the exact line):
```
{context}
```

Please:
1. Explain why this is a problem in production.
2. Provide a concrete code fix (if applicable).
3. If no fix is possible, suggest a mitigation.

Return only plain text, no markdown."""
    return prompt