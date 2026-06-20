"""LLM-powered codebase scan — reads project files with presets + rules context."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prodguardian.agents.manager import IGNORE_DIRS, TEST_DIRS

from prodguardian.llm.budget import (
    GROQ_CHUNK_THROTTLE_DEFAULT,
    GroqChunkThrottle,
    TOKEN_SAFETY_MARGIN,
    TokenBudget,
    clamp_groq_chunk_delay,
    count_tokens,
    model_input_token_limit,
    model_needs_chunk_throttle,
    model_needs_compact_guardrails,
    model_output_token_limit,
)
from prodguardian.llm.context import build_presets_context
from prodguardian.llm.llm_router import SCAN_MODE_HYBRID, ScanLLMRouter, ScanLLMSettings

ProgressCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class ScanReport:
    """Result of an LLM codebase scan with operational metadata."""

    issues: list[dict[str, Any]] = field(default_factory=list)
    files_found: int = 0
    chunks_total: int = 0
    chunks_scanned: int = 0
    api_calls: int = 0
    stopped_early: bool = False
    stop_reason: str = ""

    @property
    def llm_reached_api(self) -> bool:
        return self.api_calls > 0

    @property
    def scan_incomplete(self) -> bool:
        if self.chunks_total == 0:
            return False
        return self.stopped_early or self.chunks_scanned < self.chunks_total

# Extensions worth sending to the LLM (source + config + secrets-bearing files).
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".go", ".java", ".rb", ".php",
    ".env", ".ini", ".toml", ".yaml", ".yml", ".json", ".xml", ".conf", ".config",
    ".sh", ".bash", ".ps1", ".bat", ".md", ".txt", ".properties", ".gradle",
    ".cs", ".rs", ".kt", ".swift", ".html", ".css", ".scss",
}

SPECIAL_FILENAMES = {
    "dockerfile", "procfile", "makefile", ".env", ".env.example",
    ".env.local", ".env.production", ".env.development",
}

MAX_FILE_BYTES = 80_000
MAX_CHUNK_CHARS = 14_000
MAX_OUTPUT_TOKENS = 1200
MIN_FILE_CONTENT_TOKENS = 256

SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def _is_scannable(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in SCANNABLE_EXTENSIONS:
        return True
    if suffix == "" and name in SPECIAL_FILENAMES:
        return True
    if name.startswith(".env"):
        return True
    return False


def _should_ignore_under_root(
    path: Path,
    root: Path,
    *,
    skip_test_dirs: bool = True,
    extra_ignore_dirs: set[str] | None = None,
) -> bool:
    """Ignore dirs relative to scan root only (not e.g. Windows Temp in absolute path)."""
    try:
        rel_parts = [p.lower() for p in path.relative_to(root).parts]
    except ValueError:
        return True
    if any(d in rel_parts for d in IGNORE_DIRS):
        return True
    if extra_ignore_dirs and any(d in rel_parts for d in extra_ignore_dirs):
        return True
    if skip_test_dirs and any(d in rel_parts for d in TEST_DIRS):
        return True
    name = path.name.lower()
    if any(x in name for x in [".min.", ".bundle.", ".chunk."]):
        return True
    if name.endswith((".lock", ".map")) and not name.startswith(".env"):
        return True
    return False


def collect_scannable_files(
    root: Path,
    *,
    skip_test_dirs: bool = True,
    extra_ignore_dirs: list[str] | None = None,
) -> list[Path]:
    extra = {d.lower() for d in (extra_ignore_dirs or [])}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_ignore_under_root(
            path, root, skip_test_dirs=skip_test_dirs, extra_ignore_dirs=extra
        ):
            continue
        if not _is_scannable(path):
            continue
        files.append(path)

    def sort_key(p: Path) -> tuple[int, str]:
        name = p.name.lower()
        priority = 0
        if name.startswith(".env") or name == ".env":
            priority = 0
        elif name in {"config.py", "settings.py", "secrets", "credentials"}:
            priority = 1
        elif p.suffix.lower() in {".env", ".yaml", ".yml", ".json", ".toml"}:
            priority = 2
        else:
            priority = 3
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        return (priority, rel)

    return sorted(files, key=sort_key)


def _read_file_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if len(raw) > MAX_FILE_BYTES:
        raw = raw[:MAX_FILE_BYTES]
        truncated = True
    else:
        truncated = False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if truncated:
        text += "\n... [truncated for scan] ..."
    return text


def build_file_chunks(
    root: Path,
    files: list[Path],
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> list[list[tuple[str, str]]]:
    """Group files into LLM-sized chunks. Each entry is (relative_path, content)."""
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_size = 0

    for path in files:
        content = _read_file_text(path)
        if not content or not content.strip():
            continue
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = path.name

        block = f"--- FILE: {rel} ---\n{content}\n"
        block_len = len(block)

        if block_len > max_chunk_chars:
            if current:
                chunks.append(current)
                current = []
                current_size = 0
            chunks.append([(rel, content[:max_chunk_chars])])
            continue

        if current_size + block_len > max_chunk_chars and current:
            chunks.append(current)
            current = []
            current_size = 0

        current.append((rel, content))
        current_size += block_len

    if current:
        chunks.append(current)
    return chunks


def scan_prompt_overhead_tokens(
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    project_name: str,
    budget_model: str,
    *,
    compact_guardrails: bool = False,
) -> int:
    """Token cost of the scan prompt shell (instructions + guardrails, no file bodies)."""
    prompt = build_codebase_scan_prompt(
        [],
        presets,
        rules,
        project_name,
        compact_guardrails=compact_guardrails,
    )
    return count_tokens(prompt, budget_model)


def _file_block_tokens(rel: str, content: str, budget_model: str) -> int:
    return count_tokens(f"--- FILE: {rel} ---\n{content}\n", budget_model)


def _split_content_by_tokens(
    content: str,
    max_tokens: int,
    budget_model: str,
) -> list[str]:
    """Split file text into slices that each fit within max_tokens."""
    if max_tokens <= 0:
        return [content[:500]]

    lines = content.splitlines(keepends=True)
    if not lines:
        return [content]

    slices: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line, budget_model)
        if line_tokens > max_tokens:
            if current:
                slices.append("".join(current))
                current = []
                current_tokens = 0
            step = max(40, max_tokens * 3)
            text = line
            while text:
                piece = text[:step]
                while piece and count_tokens(piece, budget_model) > max_tokens:
                    piece = piece[: max(20, len(piece) // 2)]
                slices.append(piece)
                text = text[len(piece) :]
            continue

        if current_tokens + line_tokens > max_tokens and current:
            slices.append("".join(current))
            current = []
            current_tokens = 0

        current.append(line)
        current_tokens += line_tokens

    if current:
        slices.append("".join(current))
    return slices or [content[: max(100, max_tokens * 3)]]


def build_token_aware_chunks(
    root: Path,
    files: list[Path],
    *,
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    project_name: str,
    budget_model: str,
    max_output_tokens: int | None = None,
) -> tuple[list[list[tuple[str, str]]], bool]:
    """
    Group files into LLM chunks that respect per-model input token limits.

    Returns (chunks, used_compact_guardrails).
    """
    output_tokens = max_output_tokens or model_output_token_limit(budget_model)
    input_limit = model_input_token_limit(budget_model)

    compact = model_needs_compact_guardrails(budget_model)
    overhead = scan_prompt_overhead_tokens(
        presets, rules, project_name, budget_model, compact_guardrails=compact
    )
    content_budget = input_limit - overhead - output_tokens - TOKEN_SAFETY_MARGIN

    if content_budget < MIN_FILE_CONTENT_TOKENS:
        compact = True
        overhead = scan_prompt_overhead_tokens(
            presets, rules, project_name, budget_model, compact_guardrails=True
        )
        content_budget = input_limit - overhead - output_tokens - TOKEN_SAFETY_MARGIN

    if content_budget < MIN_FILE_CONTENT_TOKENS:
        content_budget = MIN_FILE_CONTENT_TOKENS

    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0

    for path in files:
        content = _read_file_text(path)
        if not content or not content.strip():
            continue
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = path.name

        block_tokens = _file_block_tokens(rel, content, budget_model)

        if block_tokens > content_budget:
            if current:
                chunks.append(current)
                current = []
                current_tokens = 0
            for slice_content in _split_content_by_tokens(content, content_budget, budget_model):
                chunks.append([(rel, slice_content)])
            continue

        if current_tokens + block_tokens > content_budget and current:
            chunks.append(current)
            current = []
            current_tokens = 0

        current.append((rel, content))
        current_tokens += block_tokens

    if current:
        chunks.append(current)
    return chunks, compact


def build_codebase_scan_prompt(
    files_chunk: list[tuple[str, str]],
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    project_name: str,
    *,
    compact_guardrails: bool = False,
) -> str:
    guardrails = build_presets_context(presets, rules, compact=compact_guardrails)
    files_block = "\n".join(
        f"--- FILE: {rel} ---\n{content}" for rel, content in files_chunk
    )

    return f"""You are a production security auditor reviewing code BEFORE it is pushed to GitHub.

Your job: find leaks and production risks in the files below. Focus ONLY on issues that must not ship:
- Hardcoded API keys, secrets, passwords, tokens, private keys
- .env files or env values committed to source
- Debug code (console.log, print, pdb, breakpoint, debugger)
- Localhost / dev URLs in production paths
- Exposed admin/debug endpoints
- SQL injection, unsafe eval/exec
- Permissive CORS (allow_origins="*")
- TODO/FIXME/HACK markers indicating unfinished vibe-coded code
- Dev dependencies or test tools referenced in production code

{guardrails}

Project: {project_name}

Return ONLY a JSON array (no markdown, no explanation, no trailing text). Each item:
{{
  "rule_id": "LLM001",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "file": "relative/path/from/project/root",
  "line": <line number or 0>,
  "message": "what leaked and why it must not ship",
  "code_snippet": "offending line or short excerpt"
}}

Do NOT report missing Dockerfile/README/CI — static Audit handles those.
If nothing found in these files, return: []

CODEBASE FILES:
{files_block}
"""


def build_analyzer_prompt(
    files_chunk: list[tuple[str, str]],
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    project_name: str,
    *,
    compact_guardrails: bool = False,
) -> str:
    """Hybrid phase 1 — analyzer reads chunks and records observations (not final JSON)."""
    guardrails = build_presets_context(presets, rules, compact=compact_guardrails)
    files_block = "\n".join(
        f"--- FILE: {rel} ---\n{content}" for rel, content in files_chunk
    )
    return f"""You are a senior codebase analyst preparing a production security review.

Read the files below using the user's presets and rules. Record concrete observations:
suspicious patterns, likely leaks, missing safeguards, and file locations worth flagging.
Do NOT return JSON. Use concise bullet points grouped by theme.
Format each bullet as: `relative/path:line — finding — suggested fix`.

{guardrails}

Project: {project_name}

CODEBASE FILES:
{files_block}
"""


def build_reporter_prompt(
    project_summary: str,
    files_chunks: list[list[tuple[str, str]]],
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    project_name: str,
    *,
    max_excerpt_chars: int = 8000,
) -> str:
    """Hybrid phase 2 — reporter turns analyzer notes into structured findings JSON."""
    guardrails = build_presets_context(presets, rules)
    excerpts: list[str] = []
    size = 0
    for chunk in files_chunks:
        for rel, content in chunk:
            block = f"--- FILE: {rel} ---\n{content[:2000]}\n"
            if size + len(block) > max_excerpt_chars:
                break
            excerpts.append(block)
            size += len(block)
        if size >= max_excerpt_chars:
            break
    excerpt_block = "\n".join(excerpts) if excerpts else "(see analyzer notes only)"

    return f"""You are a production security auditor producing the FINAL scan report.

You receive analyzer notes plus code excerpts. Apply the user's presets and rules.
Return ONLY a JSON array (no markdown). Each item:
{{
  "rule_id": "LLM001",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "file": "relative/path/from/project/root",
  "line": <line number or 0>,
  "message": "what leaked and why it must not ship",
  "code_snippet": "offending line or short excerpt"
}}

If nothing to report, return: []

{guardrails}

Project: {project_name}

ANALYZER NOTES:
{project_summary}

CODE EXCERPTS:
{excerpt_block}
"""


def parse_llm_scan_response(raw: str, project_root: Path) -> list[dict[str, Any]]:
    """Extract issue dicts from LLM JSON output."""
    text = raw.strip()
    if not text:
        return []

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []

    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    issues: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message", "")).strip()
        if not message:
            continue
        severity = str(item.get("severity", "HIGH")).upper()
        if severity not in SEVERITIES:
            severity = "HIGH"
        rel_file = str(item.get("file", "unknown")).replace("\\", "/")
        full_path = project_root / rel_file
        issues.append(
            {
                "rule_id": str(item.get("rule_id", "LLM001")),
                "severity": severity,
                "file": str(full_path) if full_path.exists() else rel_file,
                "line": int(item.get("line", 0) or 0),
                "message": message,
                "code_snippet": str(item.get("code_snippet", ""))[:200],
                "agent": "LLMScanner",
            }
        )
    return issues


class CodebaseLLMScanner:
    """Scan a project by sending codebase chunks + presets/rules to cloud or Ollama LLM."""

    def __init__(
        self,
        root: Path,
        presets: list[dict[str, Any]],
        rules: list[dict[str, Any]],
        *,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        scan_settings: ScanLLMSettings | None = None,
        max_cost_usd: float = 0.10,
        max_tokens: int = 32000,
        skip_test_dirs: bool = True,
        extra_ignore_dirs: list[str] | None = None,
        groq_chunk_delay: int | None = None,
    ):
        self.root = root.resolve()
        self.presets = presets
        self.rules = rules
        if scan_settings is None:
            scan_settings = ScanLLMSettings(
                mode="mono",
                mono_model=model or "gpt-3.5-turbo",
                analyzer_model=model or "gpt-3.5-turbo",
                reporter_model=model or "gpt-3.5-turbo",
                api_key=api_key,
                base_url=base_url,
            )
        self.scan_settings = scan_settings
        self.model = scan_settings.mono_model
        self._groq_chunk_delay = clamp_groq_chunk_delay(
            groq_chunk_delay
            if groq_chunk_delay is not None
            else GROQ_CHUNK_THROTTLE_DEFAULT
        )
        self._groq_throttle = GroqChunkThrottle(self._groq_chunk_delay)
        self.router = ScanLLMRouter(
            scan_settings,
            on_rate_limit_hit=self._groq_throttle.record_rate_limit,
        )
        self.budget = TokenBudget(
            max_tokens=max_tokens,
            max_cost_usd=max_cost_usd,
            enforce_session_token_cap=False,
        )
        self.skip_test_dirs = skip_test_dirs
        self.extra_ignore_dirs = extra_ignore_dirs or []
        self._compact_guardrails = model_needs_compact_guardrails(self.model)
        self._max_output_tokens = model_output_token_limit(self.model)
        self._throttle_chunks = model_needs_chunk_throttle(self.model)

    def scan(self, on_progress: ProgressCallback | None = None) -> ScanReport:
        report = ScanReport()
        stop_reason = ""

        def emit(stage: str, **data: Any) -> None:
            if on_progress:
                on_progress(stage, data)

        emit(
            "discover",
            message="Collecting source and config files for AI review",
        )
        files = collect_scannable_files(
            self.root,
            skip_test_dirs=self.skip_test_dirs,
            extra_ignore_dirs=self.extra_ignore_dirs,
        )
        report.files_found = len(files)
        emit(
            "discover",
            message=f"Found {len(files)} scannable files",
            files_total=len(files),
        )

        if not files:
            emit("llm_scan", message="No scannable files in project")
            return report

        budget_model = self.router.budget_model()
        self._max_output_tokens = model_output_token_limit(budget_model)
        self._throttle_chunks = model_needs_chunk_throttle(budget_model)
        chunks, self._compact_guardrails = build_token_aware_chunks(
            self.root,
            files,
            presets=self.presets,
            rules=self.rules,
            project_name=self.root.name,
            budget_model=budget_model,
            max_output_tokens=self._max_output_tokens,
        )
        total_chunks = len(chunks)
        report.chunks_total = total_chunks
        all_issues: list[dict[str, Any]] = []
        seen: set[tuple[str, int, str]] = set()

        mode_label = (
            f"hybrid ({self.scan_settings.analyzer_model} → "
            f"{self.scan_settings.reporter_model})"
            if self.scan_settings.is_hybrid
            else f"mono ({self.scan_settings.mono_model})"
        )
        chunk_note = (
            f" (compact guardrails, {total_chunks} token-sized chunk(s))"
            if self._compact_guardrails
            else f" — {total_chunks} chunk(s)"
        )
        emit(
            "llm_scan",
            message=f"Starting {mode_label}{chunk_note}",
            llm_provider=self.scan_settings.mode,
            llm_model=mode_label,
            chunks_total=total_chunks,
            chunks_done=0,
        )

        if self.scan_settings.mode == SCAN_MODE_HYBRID:
            stop_reason = self._scan_hybrid(
                chunks,
                emit=emit,
                seen=seen,
                all_issues=all_issues,
                budget_model=budget_model,
                report=report,
            )
        else:
            stop_reason = self._scan_mono(
                chunks,
                emit=emit,
                seen=seen,
                all_issues=all_issues,
                budget_model=budget_model,
                report=report,
            )

        report.issues = all_issues
        report.api_calls = self.router.api_calls_made()
        if stop_reason:
            report.stopped_early = True
            report.stop_reason = stop_reason
        elif report.chunks_total > 0 and report.api_calls == 0:
            report.stopped_early = True
            report.stop_reason = (
                "No API calls were made. Check your API key, model, and network connection."
            )
        emit(
            "llm_scan",
            message=(
                f"LLM pass finished — {report.api_calls} API call(s), "
                f"{report.chunks_scanned}/{report.chunks_total} chunk(s), "
                f"{len(all_issues)} finding(s)"
            ),
            chunks_done=report.chunks_scanned,
            chunks_total=report.chunks_total,
            api_calls=report.api_calls,
            issues_found=len(all_issues),
        )
        return report

    def _scan_mono(
        self,
        chunks: list[list[tuple[str, str]]],
        *,
        emit,
        seen: set[tuple[str, int, str]],
        all_issues: list[dict[str, Any]],
        budget_model: str,
        report: ScanReport,
    ) -> str:
        total_chunks = len(chunks)
        stop_reason = ""
        for idx, chunk in enumerate(chunks, start=1):
            if self._throttle_chunks and idx > 1:
                delay = self._groq_throttle.wait_before_next_chunk()
                emit(
                    "llm_scan",
                    message=f"Groq throttle: waited {delay:.0f}s before chunk {idx}",
                    chunks_done=idx - 1,
                    chunks_total=total_chunks,
                )
            file_names = self._chunk_label(chunk)
            prompt = build_codebase_scan_prompt(
                chunk,
                self.presets,
                self.rules,
                self.root.name,
                compact_guardrails=self._compact_guardrails,
            )
            budget_ok, budget_reason = self._consume_budget(
                prompt,
                budget_model,
                emit,
                idx,
                total_chunks,
                len(all_issues),
            )
            if not budget_ok:
                stop_reason = budget_reason
                break

            emit(
                "llm_scan",
                message=f"[mono] Sending chunk {idx}/{total_chunks} to LLM",
                current_file=file_names,
                chunks_done=idx - 1,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )

            response = self.router.complete_mono(
                prompt, max_tokens=self._max_output_tokens
            )
            report.chunks_scanned = idx
            if self._throttle_chunks:
                self._groq_throttle.record_success()
            self._merge_chunk_issues(
                self._parse_scan_response(response),
                seen,
                all_issues,
            )

            emit(
                "llm_scan",
                message=f"[mono] Chunk {idx}/{total_chunks} done",
                chunks_done=idx,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )
        return stop_reason

    def _scan_hybrid(
        self,
        chunks: list[list[tuple[str, str]]],
        *,
        emit,
        seen: set[tuple[str, int, str]],
        all_issues: list[dict[str, Any]],
        budget_model: str,
        report: ScanReport,
    ) -> str:
        """Analyzer pass per chunk, then one reporter pass for structured JSON."""
        total_chunks = len(chunks)
        observations: list[str] = []
        stop_reason = ""

        for idx, chunk in enumerate(chunks, start=1):
            if self._throttle_chunks and idx > 1:
                delay = self._groq_throttle.wait_before_next_chunk()
                emit(
                    "llm_scan",
                    message=f"Groq throttle: waited {delay:.0f}s before chunk {idx}",
                    chunks_done=idx - 1,
                    chunks_total=total_chunks,
                )
            file_names = self._chunk_label(chunk)
            prompt = build_analyzer_prompt(
                chunk,
                self.presets,
                self.rules,
                self.root.name,
                compact_guardrails=self._compact_guardrails,
            )
            budget_ok, budget_reason = self._consume_budget(
                prompt,
                budget_model,
                emit,
                idx,
                total_chunks,
                len(all_issues),
                output_tokens=900,
            )
            if not budget_ok:
                stop_reason = budget_reason
                break

            emit(
                "llm_scan",
                message=(
                    f"[hybrid] Analyzer reading chunk {idx}/{total_chunks} "
                    f"({self.scan_settings.analyzer_model})"
                ),
                current_file=file_names,
                chunks_done=idx - 1,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )

            notes = self.router.analyze_chunk(prompt)
            report.chunks_scanned = idx
            if self._throttle_chunks:
                self._groq_throttle.record_success()
            observations.append(f"### Chunk {idx}: {file_names}\n{notes}")

            emit(
                "llm_scan",
                message=f"[hybrid] Analyzer finished chunk {idx}/{total_chunks}",
                chunks_done=idx,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )

        if not observations:
            return stop_reason

        project_summary = "\n\n".join(observations)
        report_prompt = build_reporter_prompt(
            project_summary,
            chunks,
            self.presets,
            self.rules,
            self.root.name,
        )
        budget_ok, budget_reason = self._consume_budget(
            report_prompt,
            self.scan_settings.reporter_model,
            emit,
            total_chunks,
            total_chunks,
            len(all_issues),
        )
        if budget_ok:
            emit(
                "llm_scan",
                message=(
                    f"[hybrid] Reporter generating findings "
                    f"({self.scan_settings.reporter_model})"
                ),
                chunks_done=total_chunks,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )
            response = self.router.report_findings(
                report_prompt, max_tokens=self._max_output_tokens
            )
            if self._throttle_chunks:
                self._groq_throttle.record_success()
            self._merge_chunk_issues(
                self._parse_scan_response(response),
                seen,
                all_issues,
            )
            emit(
                "llm_scan",
                message=f"[hybrid] Reporter finished — {len(all_issues)} finding(s)",
                chunks_done=total_chunks,
                chunks_total=total_chunks,
                issues_found=len(all_issues),
            )
        else:
            stop_reason = budget_reason or stop_reason
        return stop_reason

    def _parse_scan_response(self, raw: str) -> list[dict[str, Any]]:
        """Parse LLM JSON; raise when the model response is not valid scan output."""
        text = (raw or "").strip()
        if text.lower().startswith("llm error:"):
            raise RuntimeError(text)
        issues = parse_llm_scan_response(text, self.root)
        if issues:
            return issues
        if text and "[" not in text and "{" not in text:
            raise RuntimeError(
                f"LLM returned non-JSON output (first 200 chars): {text[:200]}"
            )
        return issues

    @staticmethod
    def _chunk_label(chunk: list[tuple[str, str]]) -> str:
        file_names = ", ".join(rel for rel, _ in chunk[:3])
        if len(chunk) > 3:
            file_names += f" +{len(chunk) - 3} more"
        return file_names

    def _consume_budget(
        self,
        prompt: str,
        budget_model: str,
        emit,
        idx: int,
        total_chunks: int,
        issues_found: int,
        *,
        output_tokens: int | None = None,
    ) -> tuple[bool, str]:
        output_tokens = output_tokens or self._max_output_tokens
        prompt_tokens = count_tokens(prompt, budget_model)
        request_limit = model_input_token_limit(budget_model)
        request_total = prompt_tokens + output_tokens
        if request_total > request_limit:
            reason = (
                f"Chunk too large for {budget_model} "
                f"({request_total} tokens > {request_limit} limit). "
                "Try a model with a higher TPM limit."
            )
            emit(
                "llm_scan",
                message=reason,
                chunks_done=max(0, idx - 1),
                chunks_total=total_chunks,
                issues_found=issues_found,
            )
            return False, reason

        can_proceed, reason = self.budget.can_proceed(
            request_total,
            budget_model,
        )
        if not can_proceed:
            emit(
                "llm_scan",
                message=f"Budget limit reached: {reason}",
                chunks_done=max(0, idx - 1),
                chunks_total=total_chunks,
                issues_found=issues_found,
            )
            return False, reason
        self.budget.consume(prompt_tokens)
        return True, ""

    @staticmethod
    def _merge_chunk_issues(
        chunk_issues: list[dict[str, Any]],
        seen: set[tuple[str, int, str]],
        all_issues: list[dict[str, Any]],
    ) -> None:
        for issue in chunk_issues:
            key = (
                str(issue.get("file", "")),
                int(issue.get("line", 0)),
                str(issue.get("message", ""))[:80],
            )
            if key in seen:
                continue
            seen.add(key)
            all_issues.append(issue)