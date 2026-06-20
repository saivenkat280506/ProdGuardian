import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from prodguardian.llm.active_config import bootstrap_llm_from_disk, get_active_llm_config
from prodguardian.scan.progress import ProgressCallback, ScanProgressReporter
from prodguardian.tui.settings_store import get_presets, get_rules, get_saved_llm, get_settings, is_llm_configured
from prodguardian.utils.config import load_config

# Issues that commonly slip into vibe-coded apps and must not reach production.
VIBE_LEAK_RULES = {
    "SEC001",
    "SECRETS001",
    "LEAK001",
    "DEV001",
    "API001",
    "ENV001",
    "EXEC001",
    "SQL001",
    "FRONT001",
    "PRESET001",
    "LLM001",
}


class Orchestrator:
    def __init__(self, root_path: Optional[Path] = None):
        self.root = root_path or Path.cwd()
        self.config = load_config(self.root)
        self.scan_results = []
        self._fixer = None
        self.presets = get_presets()
        self.rules = get_rules()
        bootstrap_llm_from_disk()

    def reload_settings(self) -> None:
        self.config = load_config(self.root)
        self.presets = get_presets()
        self.rules = get_rules()
        bootstrap_llm_from_disk()
        self._fixer = None

    def update_settings(self, settings: dict) -> None:
        llm = self.config.setdefault("llm", {})
        for key in ("model", "api_key", "base_url", "provider", "max_cost_usd", "max_tokens"):
            if key in settings:
                llm[key] = settings[key]
        self._fixer = None

    def _active_llm(self) -> dict[str, str]:
        """User's saved provider/model — sole source for all backend LLM calls."""
        return get_active_llm_config()

    def _llm_budget(self) -> dict[str, float | int]:
        llm = get_settings().get("llm", {})
        return {
            "max_cost_usd": float(llm.get("max_cost_usd", 0.10)),
            "max_tokens": int(llm.get("max_tokens", 32000)),
        }

    def set_project(self, project_path: Path) -> None:
        self.root = project_path.resolve()
        self.config = load_config(self.root)

    def wants_project_picker(self, user_input: str) -> Optional[str]:
        """Return the action that needs a project picker, if any."""
        stripped = user_input.strip()
        lower = stripped.lower()

        if re.fullmatch(r"scan", lower):
            return "scan"

        if re.fullmatch(r"audit", lower):
            return "audit"

        return None

    def parse_scan_path(self, user_input: str) -> Optional[Path]:
        return self._parse_project_path(user_input, "scan")

    def parse_audit_path(self, user_input: str) -> Optional[Path]:
        return self._parse_project_path(user_input, "audit")

    def _parse_project_path(self, user_input: str, command: str) -> Optional[Path]:
        match = re.match(
            rf"^\s*{command}\s+(.+?)\s*$",
            user_input.strip(),
            re.IGNORECASE,
        )
        if not match:
            return None
        path = Path(match.group(1).strip().strip('"')).expanduser()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Project path not found or not a directory: {path}")
        return path.resolve()

    def _get_fixer(self):
        if self._fixer is None:
            from prodguardian.llm.fixer import FixGenerator
            from prodguardian.llm.router import LLMRouter

            llm = self._active_llm()
            budget = self._llm_budget()

            if llm["provider"] != "ollama" and not llm.get("api_key"):
                raise ValueError(
                    "No API key configured. Open Settings or click Scan to set up Cloud API or Ollama."
                )

            fixer = FixGenerator(
                model=llm["model"],
                max_cost_usd=float(budget["max_cost_usd"]),
            )
            fixer.budget.max_tokens = int(budget["max_tokens"])
            fixer.presets = self.presets
            fixer.rules = self.rules
            fixer.router = LLMRouter(
                model=llm["model"],
                api_key=llm["api_key"],
                base_url=llm.get("base_url") or None,
            )
            self._fixer = fixer
        return self._fixer

    async def handle(
        self,
        user_input: str,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        lower = user_input.lower()

        if re.search(r"\b(settings|config|configure|api key|setup)\b", lower):
            return "__OPEN_SETTINGS__"

        if re.fullmatch(r"scan", lower):
            return "__PICK_PROJECT__:scan"

        scan_path = self.parse_scan_path(user_input)
        if scan_path is not None:
            self.set_project(scan_path)
            return await self._run_scan(on_progress=on_progress)

        if re.search(r"\b(scan|security|vulnerab|issue|find problems)\b", lower):
            return await self._run_scan(on_progress=on_progress)

        elif re.fullmatch(r"audit", lower):
            return "__PICK_PROJECT__:audit"

        audit_path = self.parse_audit_path(user_input)
        if audit_path is not None:
            self.set_project(audit_path)
            return await self._run_audit()

        elif re.search(r"\b(audit|production readiness|production ready)\b", lower):
            return await self._run_audit()
        elif re.search(r"\b(missing dockerfile|missing ci|no ci pipeline)\b", lower):
            return await self._run_audit()

        elif re.search(r"\b(generate|create|make)\s+(docker|ci|env|compose)", lower):
            asset_match = re.search(r"(docker|ci|env|compose)", lower)
            asset = asset_match.group(1) if asset_match else None
            return await self._generate_asset(asset)

        elif re.search(r"\b(fix|resolve|correct|help with)\b", lower):
            match = re.search(r"(\w+)\s+in\s+(\S+)\s+line\s+(\d+)", lower)
            if match:
                rule, file_path, line = match.groups()
                issue = {
                    "rule_id": rule,
                    "file": file_path,
                    "line": int(line),
                    "message": f"Issue {rule}",
                    "severity": "HIGH",
                }
                try:
                    fixer = self._get_fixer()
                    fix = fixer.generate_fix(issue)
                    return f"**Suggested fix:**\n```\n{fix}\n```\n\nReview before applying."
                except ValueError as e:
                    return f"Error: {e}"
                except Exception as e:
                    return f"Error generating fix: {e}"
            else:
                return "Please specify the issue like: `fix SEC001 in config.py line 42`"

        elif re.search(r"\b(explain|what is|tell me about)\b", lower):
            match = re.search(r"(\w+)\s+in\s+(\S+)\s+line\s+(\d+)", lower)
            if match:
                rule, file_path, line = match.groups()
                issue = {
                    "rule_id": rule,
                    "file": file_path,
                    "line": int(line),
                    "message": f"Issue {rule}",
                }
                try:
                    fixer = self._get_fixer()
                    explanation = fixer.explain(issue)
                    return explanation
                except ValueError as e:
                    return f"Error: {e}"
                except Exception as e:
                    return f"Error: {e}"
            else:
                return "Specify issue like: `explain SEC001 in config.py line 42`"

        elif re.fullmatch(r"project", lower):
            return f"Current project: [cyan]{self.root}[/cyan]"

        elif re.search(r"\b(help|commands|what can you do)\b", lower):
            return self._help_text()

        else:
            return self._help_text()

    def _help_text(self) -> str:
        llm = self._active_llm()
        model = llm.get("model", "not set")
        if llm.get("provider") == "ollama":
            key_status = "ollama (local)"
        elif llm.get("api_key"):
            key_status = "set"
        else:
            key_status = "not set"

        return (
            "I am a production readiness assistant. I can:\n\n"
            "- [bold]Scan[/bold] uses your Cloud API or Ollama to read the codebase "
            "with your presets & rules (secrets, env files, debug code, etc.)\n"
            "- [bold]Audit[/bold] missing production assets (Dockerfile, CI, env)\n"
            "- [bold]Generate[/bold] Dockerfile, CI, env.example, docker-compose\n"
            "- [bold]Fix[/bold] or [bold]explain[/bold] specific issues (requires API key)\n"
            "- [bold]Settings[/bold] (Ctrl+comma) - AI provider, presets, rules, scan options\n\n"
            f"Current: model=[cyan]{model}[/cyan], provider=[cyan]{key_status}[/cyan]\n\n"
            "Use the [cyan]Scan[/cyan] and [cyan]Audit[/cyan] buttons, or "
            "[bold]Ctrl+S[/bold] / [bold]Ctrl+,[/bold] for shortcuts.\n\n"
            "Press [bold]Ctrl+comma[/bold] to open Settings."
        )

    def _relative_file(self, file_path: str | Path) -> str:
        try:
            return str(Path(file_path).resolve().relative_to(self.root))
        except ValueError:
            return str(file_path)

    def _format_issue_line(self, issue: dict) -> str:
        rel_file = self._relative_file(issue.get("file", ""))
        return (
            f"  - `{issue.get('rule_id', '?')}` in {rel_file}:{issue.get('line', '?')}: "
            f"{issue.get('message', '')}\n"
        )

    def _llm_status_payload(self) -> dict[str, Any]:
        """Report AI provider used to read the codebase during scan."""
        saved = get_saved_llm()
        configured = is_llm_configured()
        provider = saved.get("provider", "api")
        model = saved.get("model", "not set")
        preset_count = len([p for p in self.presets if p.get("enabled", True)])
        rule_count = len([r for r in self.rules if r.get("enabled", True)])
        from prodguardian.llm.active_config import get_scan_llm_settings

        scan_cfg = get_scan_llm_settings()
        mode_desc = scan_cfg.describe()
        if configured and provider == "ollama":
            message = (
                f"Scan {mode_desc} will read your codebase locally "
                f"with {preset_count} preset(s) and {rule_count} rule(s)."
            )
        elif configured:
            message = (
                f"Scan {mode_desc} will analyze your codebase "
                f"with {preset_count} preset(s) and {rule_count} rule(s)."
            )
        else:
            message = "No AI provider configured. Scan requires Cloud API or Ollama."
        return {
            "message": message,
            "llm_configured": configured,
            "llm_provider": provider,
            "llm_model": model,
            "scan_uses_llm": configured,
            "preset_count": preset_count,
        }

    def _scan_options(self) -> dict[str, Any]:
        return self.config.get("scan", {})

    def _build_llm_scanner(self):
        from prodguardian.llm.active_config import get_scan_llm_settings
        from prodguardian.llm.codebase_scanner import CodebaseLLMScanner

        scan_settings = get_scan_llm_settings()
        budget = self._llm_budget()
        scan_cfg = self._scan_options()
        return CodebaseLLMScanner(
            self.root,
            self.presets,
            self.rules,
            scan_settings=scan_settings,
            max_cost_usd=float(budget["max_cost_usd"]),
            max_tokens=int(budget["max_tokens"]),
            skip_test_dirs=scan_cfg.get("skip_test_dirs", True),
            extra_ignore_dirs=scan_cfg.get("ignore_dirs", []),
            groq_chunk_delay=scan_cfg.get("groq_chunk_delay"),
        )

    @staticmethod
    def _merge_issues(*issue_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[tuple[str, int, str]] = set()
        for issues in issue_lists:
            for issue in issues:
                key = (
                    str(issue.get("file", "")),
                    int(issue.get("line", 0) or 0),
                    str(issue.get("message", ""))[:80],
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(issue)
        return merged

    def _run_static_scan(
        self,
        on_progress: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        """Fast local scan — presets + agents, no API calls."""
        from prodguardian.agents.manager import AgentManager
        from prodguardian.llm.codebase_scanner import _should_ignore_under_root
        from prodguardian.scan.preset_scanner import scan_tree_presets

        scan_cfg = self._scan_options()
        skip_test_dirs = scan_cfg.get("skip_test_dirs", True)
        extra_ignore = {d.lower() for d in scan_cfg.get("ignore_dirs", [])}

        def should_ignore(path: Path) -> bool:
            return _should_ignore_under_root(
                path,
                self.root,
                skip_test_dirs=skip_test_dirs,
                extra_ignore_dirs=extra_ignore,
            )

        preset_issues = scan_tree_presets(
            self.root,
            self.presets,
            should_ignore,
            on_progress=on_progress,
        )
        manager = AgentManager(
            self.root,
            skip_test_dirs=skip_test_dirs,
            extra_ignore_dirs=list(extra_ignore),
        )
        agent_issues = manager.scan(on_progress=on_progress)
        return self._merge_issues(preset_issues, agent_issues)

    def _run_scan_blocking(self, on_progress: ProgressCallback | None = None) -> str:
        reporter = ScanProgressReporter(on_progress=on_progress)
        issues: list[dict[str, Any]] = []
        llm_report = None

        try:
            reporter.emit("init", message=f"Starting scan of {self.root}")

            reporter.emit(
                "static_scan",
                message="Running local preset + agent scan (no API)",
            )
            static_issues = self._run_static_scan(on_progress=reporter.emit)
            reporter.emit(
                "static_scan",
                message=f"Local scan found {len(static_issues)} issue(s)",
                issues_found=len(static_issues),
            )

            if not is_llm_configured():
                reporter.emit("llm_status", **self._llm_status_payload())
                issues = static_issues
                self.scan_results = issues
                reporter.add_issues(len(issues))
                reporter.emit(
                    "done",
                    message=f"Scan finished — {len(issues)} issue(s) (local only, no AI)",
                    issues_found=len(issues),
                )
                if not issues:
                    return (
                        f"Scanned [cyan]{self.root}[/cyan] — no leaks found locally. "
                        "Configure Cloud API or Ollama for deeper AI review."
                    )
                return self._format_scan_summary(issues, llm_api_calls=0, llm_incomplete=False)

            bootstrap_llm_from_disk()
            reporter.emit("llm_status", **self._llm_status_payload())

            from prodguardian.llm.active_config import get_scan_llm_settings
            from prodguardian.llm.llm_router import prepare_scan_models

            scan_settings = get_scan_llm_settings()
            ollama_error = prepare_scan_models(
                scan_settings,
                on_progress=lambda msg: reporter.emit(
                    "llm_status",
                    message=str(msg),
                ),
            )
            if ollama_error:
                reporter.emit("done", message=ollama_error)
                return f"Scan error: {ollama_error}"

            scanner = self._build_llm_scanner()
            llm_report = scanner.scan(on_progress=reporter.emit)

            if llm_report.chunks_total > 0 and not llm_report.llm_reached_api:
                reporter.emit("done", message=llm_report.stop_reason or "LLM scan made no API calls")
                return (
                    f"[bold red]AI scan did not reach the API.[/bold red]\n\n"
                    f"{llm_report.stop_reason or 'No API calls were recorded.'}\n\n"
                    f"Local scan still found [cyan]{len(static_issues)}[/cyan] issue(s). "
                    "Check Settings → API key, model, and Groq dashboard for the same key.\n\n"
                    + (
                        self._format_scan_summary(static_issues, llm_api_calls=0, llm_incomplete=True)
                        if static_issues
                        else ""
                    )
                )

            issues = self._merge_issues(static_issues, llm_report.issues)
            self.scan_results = issues
            reporter.add_issues(len(issues))

            reporter.emit(
                "aggregate",
                message="Grouping findings by severity",
                issues_found=len(issues),
            )
            done_msg = (
                f"Scan finished — {len(issues)} issue(s) "
                f"({llm_report.api_calls} API call(s), "
                f"{llm_report.chunks_scanned}/{llm_report.chunks_total} AI chunks)"
            )
            if llm_report.scan_incomplete:
                done_msg += f" — AI pass incomplete: {llm_report.stop_reason}"
            reporter.emit("done", message=done_msg, issues_found=len(issues))
        except Exception as e:
            reporter.emit("done", message=f"Scan failed: {e}")
            return f"Scan error: {e}"

        if not issues:
            return (
                f"Scanned [cyan]{self.root}[/cyan] — no vibe-coded leaks found. "
                "Your project looks clean for production."
            )

        return self._format_scan_summary(
            issues,
            llm_api_calls=llm_report.api_calls if llm_report else 0,
            llm_incomplete=bool(llm_report and llm_report.scan_incomplete),
            llm_stop_reason=llm_report.stop_reason if llm_report else "",
        )

    def _format_scan_summary(
        self,
        issues: list[dict[str, Any]],
        *,
        llm_api_calls: int = 0,
        llm_incomplete: bool = False,
        llm_stop_reason: str = "",
    ) -> str:

        vibe_leaks = [i for i in issues if i.get("rule_id") in VIBE_LEAK_RULES]
        other_issues = [i for i in issues if i.get("rule_id") not in VIBE_LEAK_RULES]

        summary = f"Scanned [cyan]{self.root}[/cyan]\n\n"

        if llm_incomplete and llm_stop_reason:
            summary += (
                f"[bold yellow]Note:[/bold yellow] AI pass did not finish all chunks "
                f"({llm_stop_reason}). Local + partial AI results are shown.\n\n"
            )

        if vibe_leaks:
            summary += (
                f"[bold]Found {len(vibe_leaks)} vibe-coded leak(s)[/bold] "
                "that should not ship to production:\n\n"
            )
            for severity, label in (
                ("CRITICAL", "[bold red]CRITICAL[/bold red]"),
                ("HIGH", "[bold yellow]HIGH[/bold yellow]"),
                ("MEDIUM", "[bold blue]MEDIUM[/bold blue]"),
            ):
                bucket = [i for i in vibe_leaks if i.get("severity") == severity]
                if not bucket:
                    continue
                summary += f"{label} ({len(bucket)}):\n"
                for issue in bucket[:8]:
                    summary += self._format_issue_line(issue)
                if len(bucket) > 8:
                    summary += f"  - ...and {len(bucket) - 8} more\n"
                summary += "\n"
        else:
            summary += "No vibe-coded leak rules triggered, but other security issues were found.\n\n"

        if other_issues:
            summary += f"[dim]Also found {len(other_issues)} other security issue(s).[/dim]\n"

        llm = get_saved_llm()
        api_note = (
            f", {llm_api_calls} AI API call(s)"
            if llm_api_calls
            else ", local scan only (no AI API calls)"
        )
        summary += (
            f"\n[dim]Scanned with presets/rules"
            f"{api_note}"
            f" — model {llm.get('provider', 'api')} / {llm.get('model', '')}[/dim]\n"
            "To get a fix for an issue, use: `fix LLM001 in path/to/file.py line 42`"
        )
        return summary

    async def _run_scan(self, on_progress: ProgressCallback | None = None) -> str:
        return await asyncio.to_thread(self._run_scan_blocking, on_progress)

    def _format_audit_report(self, missing: list[dict[str, Any]]) -> str:
        """Rich-text audit report for the TUI results page."""
        header = f"[bold]Production Audit[/bold] — [cyan]{self.root}[/cyan]\n"

        if not missing:
            return (
                f"{header}\n"
                "[bold green]PASSED[/bold green] — all required production assets are present.\n\n"
                "[dim]Static audit checks file presence and basic config. "
                "Use Scan for deep AI content analysis (secrets in code, SQLi, XSS, etc.).[/dim]"
            )

        severity_style = {
            "CRITICAL": "bold red",
            "HIGH": "bold yellow",
            "MEDIUM": "bold blue",
            "LOW": "dim",
        }

        lines = [
            header,
            f"[bold yellow]FAILED[/bold yellow] — {len(missing)} missing or incomplete item(s):\n",
        ]
        for item in missing:
            rule_id = item.get("rule_id", "PROD???")
            severity = str(item.get("severity", "HIGH")).upper()
            style = severity_style.get(severity, "bold yellow")
            message = item.get("message", "Issue found")
            location = item.get("file") or "project root"
            lines.append(f"[{style}]{severity}[/{style}]  [bold]{rule_id}[/bold]  {message}")
            lines.append(f"         [dim]→ {location}[/dim]")
            fix_hint = item.get("fix_hint")
            if fix_hint:
                lines.append(f"         [cyan]Fix:[/cyan] {fix_hint}")
            lines.append("")

        lines.append("[bold]Quick actions[/bold]")
        seen_commands: set[str] = set()
        for item in missing:
            cmd = item.get("generate_command")
            if cmd and cmd not in seen_commands:
                seen_commands.add(cmd)
                lines.append(f"  • CLI: [cyan]prodguardian {cmd}[/cyan]")
        if not seen_commands:
            lines.append("  • [dim]No auto-generators for these items — apply fix hints above.[/dim]")
        lines.append(
            "\n[dim]Tip: Run [cyan]Scan[/cyan] for AI deep-dive on code content "
            "(secrets, injection, XSS). Audit covers files and baseline config.[/dim]"
        )

        return "\n".join(lines)

    def _run_audit_blocking(self, on_progress: ProgressCallback | None = None) -> str:
        try:
            from prodguardian.production.auditor import ProductionAuditor

            auditor = ProductionAuditor(self.root)
            missing = auditor.audit(on_progress=on_progress)
        except Exception as e:
            if on_progress:
                on_progress("done", {"message": f"Audit failed: {e}"})
            return f"[bold red]Audit error:[/bold red] {e}"

        return self._format_audit_report(missing)

    async def _run_audit(self, on_progress: ProgressCallback | None = None) -> str:
        return await asyncio.to_thread(self._run_audit_blocking, on_progress)

    async def _generate_asset(self, asset_type: Optional[str]) -> str:
        if not asset_type:
            return "Specify what to generate: `dockerfile`, `ci`, `env`, or `compose`."

        root = self.root
        try:
            from prodguardian.production.generator import (
                generate_docker_compose,
                generate_dockerfile,
                generate_env_example,
                generate_github_ci,
            )

            if asset_type == "docker":
                out_path = root / "Dockerfile"
                if out_path.exists():
                    return f"`{out_path}` already exists."
                generate_dockerfile(root, out_path)
                return f"Generated `{out_path}`\n\nYou can now run `docker build -t myapp .`"

            elif asset_type == "ci":
                out_path = root / ".github" / "workflows" / "ci.yml"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if out_path.exists():
                    return f"`{out_path}` already exists."
                generate_github_ci(root, out_path)
                return f"Generated GitHub Actions workflow at `{out_path}`"

            elif asset_type == "env":
                out_path = root / ".env.example"
                if out_path.exists():
                    return f"`{out_path}` already exists."
                generate_env_example(root, out_path)
                return f"Generated `{out_path}` - copy to `.env` and fill in values."

            elif asset_type == "compose":
                out_path = root / "docker-compose.yml"
                if out_path.exists():
                    return f"`{out_path}` already exists."
                generate_docker_compose(root, out_path)
                return f"Generated `{out_path}`"

            else:
                return f"Unknown asset `{asset_type}`. Try `dockerfile`, `ci`, `env`, or `compose`."

        except Exception as e:
            return f"Error generating {asset_type}: {e}"