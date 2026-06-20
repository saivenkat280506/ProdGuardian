import concurrent.futures
import os
from pathlib import Path
from typing import Any, Callable, Optional

from .backend_agent import BackendAgent
from .frontend_agent import FrontendAgent
from .secrets_agent import SecretsAgent

AGENTS = [FrontendAgent(), BackendAgent(), SecretsAgent()]

# Dirs to completely skip (any path segment match). Keep this lean for prod scans.
IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env", ".env",
    "dist", "build", "target", ".prodguardian_cache", ".cache",
    "site-packages", ".next", ".nuxt", "coverage", ".pytest_cache",
    "htmlcov", ".mypy_cache", ".ruff_cache", "tmp", "temp",
}

# Common test dirs - security findings inside tests/fixtures are often intentional examples.
# Skip by default for cleaner "prod" signal (use skip_test_dirs=False to force include).
TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "testdata"}


def _should_ignore(
    path: Path,
    skip_test_dirs: bool = True,
    extra_ignore_dirs: Optional[set[str]] = None,
) -> bool:
    parts = [p.lower() for p in path.parts]
    if any(d in parts for d in IGNORE_DIRS):
        return True
    if extra_ignore_dirs and any(d in parts for d in extra_ignore_dirs):
        return True
    if skip_test_dirs and any(d in parts for d in TEST_DIRS):
        return True
    # Skip very large generated / minified files
    name = path.name.lower()
    if any(x in name for x in [".min.", ".bundle.", ".chunk."]):
        return True
    if name.endswith((".lock", ".map")) and not name.startswith(".env"):
        return True
    return False


def _scan_file(file_path: Path) -> list[dict[str, Any]]:
    """Worker function. Thread-safe (no pickling requirement)."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    issues = []
    for agent in AGENTS:
        if agent.can_handle(file_path):
            try:
                agent_issues = agent.scan(file_path, content)
                for iss in agent_issues:
                    if "agent" not in iss:
                        iss["agent"] = agent.name
                issues.extend(agent_issues)
            except Exception:
                pass
    return issues


class AgentManager:
    def __init__(
        self,
        root_path: Path,
        parallel_workers: Optional[int] = None,
        skip_test_dirs: bool = True,
        extra_ignore_dirs: Optional[list[str]] = None,
    ):
        self.root_path = root_path
        self.parallel_workers = parallel_workers or max(1, min(8, (os.cpu_count() or 2)))
        self.skip_test_dirs = skip_test_dirs
        self.extra_ignore_dirs = {d.lower() for d in (extra_ignore_dirs or [])}

    def _get_files(self) -> list[Path]:
        files = []
        for p in self.root_path.rglob("*"):
            if not p.is_file():
                continue
            if _should_ignore(
                p,
                skip_test_dirs=self.skip_test_dirs,
                extra_ignore_dirs=self.extra_ignore_dirs,
            ):
                continue
            files.append(p)
        return files

    def scan(
        self,
        on_progress: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        files = self._get_files()
        all_issues: list[dict[str, Any]] = []
        total = len(files)

        if on_progress:
            on_progress(
                "agents",
                {
                    "message": "Running SecretsAgent, BackendAgent, FrontendAgent in parallel",
                    "files_total": total,
                    "files_done": 0,
                    "issues_found": 0,
                    "workers": self.parallel_workers,
                },
            )

        if not files:
            return all_issues

        done = 0
        # ThreadPool: robust on Windows (no spawn/__main__ issues), works from any script/Jupyter/CLI.
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            future_to_file = {executor.submit(_scan_file, f): f for f in files}
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                done += 1
                try:
                    issues = future.result()
                    all_issues.extend(issues)
                except Exception as e:
                    print(f"[agent] Error scanning {file}: {e}")
                    issues = []

                if on_progress:
                    try:
                        rel = str(file.relative_to(self.root_path))
                    except ValueError:
                        rel = str(file)
                    agents_used = ", ".join(a.name for a in AGENTS if a.can_handle(file))
                    on_progress(
                        "agents",
                        {
                            "message": f"Scanning {rel}",
                            "files_total": total,
                            "files_done": done,
                            "current_file": rel,
                            "agent": agents_used or "skip",
                            "issues_found": len(all_issues),
                        },
                    )
        return all_issues
