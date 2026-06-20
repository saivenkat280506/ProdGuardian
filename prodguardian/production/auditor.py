"""Static production-readiness audit — fast, non-AI checklist."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from prodguardian.agents.manager import IGNORE_DIRS
from prodguardian.production.audit_fixes import enrich_audit_issue
from prodguardian.utils.framework_detect import detect_framework

AuditProgressCallback = Callable[[str, dict[str, Any]], None]

# File globs scanned for pattern-based checks.
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rb", ".php", ".cs"}
_CONFIG_NAMES = {
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "nginx.conf", "compose.yml", "compose.yaml",
}


class ProductionAuditor:
    """Check for missing production assets and common static misconfigurations."""

    def __init__(self, root: Path):
        self.root = root
        self.framework_info = detect_framework(root)
        self._text_files: list[Path] | None = None
        self._on_progress: AuditProgressCallback | None = None

    def audit(
        self,
        on_progress: AuditProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        self._on_progress = on_progress

        def emit(stage: str, **data: Any) -> None:
            if self._on_progress:
                self._on_progress(stage, data)

        issues: list[dict[str, Any]] = []
        emit("init", message=f"Starting production audit of {self.root}")

        emit("core", message="Checking Dockerfile, CI, env files, and docs...")
        issues.extend(self._check_core_assets())

        runtime_checks = [
            ("Error handlers", self._check_error_handling),
            ("Rate limiting", self._check_rate_limiting),
            ("Health endpoints", self._check_health_endpoints),
            ("Structured logging", self._check_structured_logging),
            ("Database pooling", self._check_db_pooling),
            ("Frontend production build", self._check_frontend_production_build),
            ("API documentation", self._check_api_documentation),
        ]
        for idx, (label, checker) in enumerate(runtime_checks, start=1):
            emit(
                "runtime",
                message=f"Checking {label}... ({idx}/{len(runtime_checks)})",
                detail=label,
            )
            issues.extend(checker())

        security_checks = [
            ("Security headers", self._check_security_headers),
            ("Secrets practices", self._check_secrets_practices),
            ("Docker hardening", self._check_docker_hardening),
            ("CORS configuration", self._check_cors_wildcard),
        ]
        for idx, (label, checker) in enumerate(security_checks, start=1):
            emit(
                "security",
                message=f"Checking {label}... ({idx}/{len(security_checks)})",
                detail=label,
            )
            issues.extend(checker())

        emit("ops", message="Checking monitoring...")
        issues.extend(self._check_monitoring())
        emit("ops", message="Checking backup strategy...")
        issues.extend(self._check_backup_strategy())

        emit("report", message="Building audit report", issues_found=len(issues))
        result = [enrich_audit_issue(issue) for issue in issues]
        emit(
            "done",
            message=f"Audit finished — {len(result)} finding(s)",
            issues_found=len(result),
        )
        return result

    # ------------------------------------------------------------------
    # PROD001–PROD008: original checks
    # ------------------------------------------------------------------

    def _check_core_assets(self) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []

        if not (self.root / "Dockerfile").exists():
            issues.append(self._issue(
                "PROD001", "HIGH", "Dockerfile (missing)", 0,
                "Missing Dockerfile - cannot containerize",
            ))

        if not (self.root / "docker-compose.yml").exists():
            issues.append(self._issue(
                "PROD002", "MEDIUM", "docker-compose.yml (missing)", 0,
                "Missing docker-compose.yml - local dev may be harder",
            ))

        ci_path = self.root / ".github" / "workflows" / "ci.yml"
        if not ci_path.exists():
            issues.append(self._issue(
                "PROD003", "HIGH", ".github/workflows/ci.yml (missing)", 0,
                "No CI pipeline - automated testing missing",
            ))

        if not (self.root / ".env.example").exists():
            issues.append(self._issue(
                "PROD004", "MEDIUM", ".env.example (missing)", 0,
                "Missing .env.example - environment variables not documented",
            ))

        if not (self.root / "README.md").exists() and not (self.root / "README.rst").exists():
            issues.append(self._issue(
                "PROD007", "LOW", "README.md (missing)", 0,
                "Missing README - project documentation absent",
            ))

        if not (self.root / ".gitignore").exists():
            issues.append(self._issue(
                "PROD008", "LOW", ".gitignore (missing)", 0,
                "Missing .gitignore - sensitive files may be committed",
            ))
        return issues

    def _check_error_handling(self) -> list[dict[str, Any]]:
        fw = self.framework_info.get("web_framework")
        if fw == "flask":
            if not self._grep_sources(r"app\.errorhandler|@app\.errorhandler"):
                return [self._issue(
                    "PROD005", "HIGH", "app.py (missing error handler)", 0,
                    "No global error handler - unhandled exceptions may crash app",
                )]
        elif fw == "express":
            if not self._grep_sources(r"app\.use\(\(err|\.on\(['\"]error"):
                return [self._issue(
                    "PROD005", "HIGH", "app.js (missing error handler)", 0,
                    "No global error handler - unhandled exceptions may crash app",
                )]
        elif fw == "fastapi":
            if not self._grep_sources(r"@app\.exception_handler|exception_handler"):
                return [self._issue(
                    "PROD005", "HIGH", "(missing error handler)", 0,
                    "No FastAPI exception handler - errors may leak internals",
                )]
        return []

    def _check_rate_limiting(self) -> list[dict[str, Any]]:
        if not self.framework_info.get("web_framework"):
            return []
        if self._grep_sources(r"limiter|ratelimit|rate_limit|slowapi|express-rate-limit"):
            return []
        return [self._issue(
            "PROD006", "MEDIUM", "(missing rate limiting)", 0,
            "No rate limiting detected - API may be vulnerable to abuse",
        )]

    # ------------------------------------------------------------------
    # PROD009–PROD020: expanded static checks
    # ------------------------------------------------------------------

    def _check_security_headers(self) -> list[dict[str, Any]]:
        """PROD009: Security headers middleware or explicit header configuration."""
        patterns = [
            r"helmet\(", r"secure_headers", r"SecureHeaders", r"X-Frame-Options",
            r"Content-Security-Policy", r"Strict-Transport-Security",
            r"add_header\s+Strict-Transport", r"add_header\s+X-Frame",
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        return [self._issue(
            "PROD009", "HIGH", "(missing security headers)", 0,
            "No security headers middleware detected (helmet, CSP, HSTS, X-Frame-Options)",
        )]

    def _check_health_endpoints(self) -> list[dict[str, Any]]:
        """PROD010: Health/readiness/liveness endpoints for orchestrators."""
        patterns = [
            r"/health", r"/healthz", r"/ready", r"/readiness", r"/live", r"/liveness",
            r"@app\.get\(['\"]/health", r"health_check", r"HealthCheck",
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        if not self.framework_info.get("web_framework"):
            return []
        return [self._issue(
            "PROD010", "HIGH", "(missing health check)", 0,
            "No health/readiness endpoint - load balancers cannot verify app status",
        )]

    def _check_structured_logging(self) -> list[dict[str, Any]]:
        """PROD011: Structured JSON logging instead of plain print statements."""
        patterns = [
            r"structlog", r"JSONFormatter", r"pythonjsonlogger", r"winston\.format\.json",
            r"pino\(", r"bunyan", r"logging\.config", r'format.*"json"',
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        if self.framework_info.get("type") == "unknown":
            return []
        return [self._issue(
            "PROD011", "MEDIUM", "(missing structured logging)", 0,
            "No structured logging detected - use JSON logs for production observability",
        )]

    def _check_secrets_practices(self) -> list[dict[str, Any]]:
        """PROD012: Secrets management and .env hygiene."""
        issues: list[dict[str, Any]] = []

        env_file = self.root / ".env"
        if env_file.exists():
            issues.append(self._issue(
                "PROD012", "CRITICAL", ".env", 0,
                ".env file present in project - ensure it is gitignored and never committed",
            ))

        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            try:
                gi = gitignore.read_text(encoding="utf-8", errors="ignore").lower()
                if ".env" not in gi and "*.env" not in gi:
                    issues.append(self._issue(
                        "PROD012", "HIGH", ".gitignore", 0,
                        ".gitignore does not exclude .env files - secrets may be committed",
                    ))
            except OSError:
                pass

        if not self._grep_sources(r"vault|doppler|secretsmanager|secretmanager|aws-secrets|infisical"):
            if (self.root / ".env.example").exists() and not issues:
                issues.append(self._issue(
                    "PROD012", "MEDIUM", "(secrets management)", 0,
                    "No secrets manager integration hinted - consider Vault, Doppler, or cloud SM",
                ))
        return issues

    def _check_db_pooling(self) -> list[dict[str, Any]]:
        """PROD013: Database connection pooling for production workloads."""
        patterns = [
            r"create_pool", r"pool_size", r"max_overflow", r"pgbouncer",
            r"connection_pool", r"Pool\(", r"sqlalchemy\.pool", r"prisma.*pool",
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        db_hints = self._grep_sources(r"postgres|mysql|mongodb|sqlite|prisma|sqlalchemy|mongoose")
        if not db_hints:
            return []
        return [self._issue(
            "PROD013", "MEDIUM", "(missing connection pooling)", 0,
            "Database used but no connection pooling detected - risk of connection exhaustion",
        )]

    def _check_frontend_production_build(self) -> list[dict[str, Any]]:
        """PROD014: Frontend production build configuration."""
        pkg = self.root / "package.json"
        if not pkg.exists():
            return []

        try:
            content = pkg.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        issues: list[dict[str, Any]] = []
        scripts = content.lower()
        if '"build"' not in scripts and "'build'" not in scripts:
            issues.append(self._issue(
                "PROD014", "HIGH", "package.json", 0,
                "No npm build script - frontend may ship development bundles",
            ))

        if self._grep_sources(r"sourceMappingURL|devtool:\s*['\"]source-map"):
            issues.append(self._issue(
                "PROD014", "MEDIUM", "(source maps in prod)", 0,
                "Source maps referenced - disable in production builds to avoid code exposure",
            ))
        return issues

    def _check_api_documentation(self) -> list[dict[str, Any]]:
        """PROD015: OpenAPI/Swagger or equivalent API documentation."""
        if not self.framework_info.get("web_framework"):
            return []
        patterns = [
            r"openapi", r"swagger", r"redoc", r"/docs", r"FastAPI\(",
            r"@app\.get\(['\"]/docs", r"api-docs", r"Scalar\(",
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        return [self._issue(
            "PROD015", "MEDIUM", "(missing API docs)", 0,
            "No API documentation detected (OpenAPI/Swagger /docs endpoint)",
        )]

    def _check_monitoring(self) -> list[dict[str, Any]]:
        """PROD016: Monitoring, error tracking, or observability integration."""
        patterns = [
            r"sentry", r"prometheus", r"opentelemetry", r"datadog", r"newrelic",
            r"honeycomb", r"grafana", r"statsd", r"@opentelemetry",
        ]
        if self._grep_sources("|".join(patterns)):
            return []
        if self.framework_info.get("type") == "unknown":
            return []
        return [self._issue(
            "PROD016", "MEDIUM", "(missing observability)", 0,
            "No monitoring/observability integration (Sentry, Prometheus, OpenTelemetry, etc.)",
        )]

    def _check_backup_strategy(self) -> list[dict[str, Any]]:
        """PROD017: Backup or disaster-recovery documentation/scripts."""
        patterns = [
            r"backup", r"snapshot", r"point-in-time", r"disaster.recovery",
            r"pg_dump", r"mysqldump", r"restore",
        ]
        for path in self._iter_text_files():
            name = path.name.lower()
            if name in {"readme.md", "readme.rst", "docs.md", "operations.md", "runbook.md"}:
                try:
                    if re.search("|".join(patterns), path.read_text(encoding="utf-8", errors="ignore"), re.I):
                        return []
                except OSError:
                    continue
            if "backup" in name or "restore" in name:
                return []
        if self._grep_sources("|".join(patterns)):
            return []
        return [self._issue(
            "PROD017", "LOW", "(missing backup strategy)", 0,
            "No backup/disaster-recovery documentation or scripts detected",
        )]

    def _check_docker_hardening(self) -> list[dict[str, Any]]:
        """PROD018: Dockerfile runs as non-root with pinned base images."""
        dockerfile = self.root / "Dockerfile"
        if not dockerfile.exists():
            return []
        try:
            content = dockerfile.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        issues: list[dict[str, Any]] = []
        if not re.search(r"^USER\s+", content, re.MULTILINE | re.IGNORECASE):
            issues.append(self._issue(
                "PROD018", "HIGH", "Dockerfile", 0,
                "Dockerfile does not set USER - container likely runs as root",
            ))
        if re.search(r":latest\b", content, re.IGNORECASE):
            issues.append(self._issue(
                "PROD018", "MEDIUM", "Dockerfile", 0,
                "Dockerfile uses :latest tag - pin image versions for reproducible builds",
            ))
        return issues

    def _check_cors_wildcard(self) -> list[dict[str, Any]]:
        """PROD019: Permissive CORS wildcard configuration."""
        patterns = [
            r'allow_origins=\[\"\*\"\]', r"allow_origins=\['\*'\]",
            r"CORS\(.*\*", r"Access-Control-Allow-Origin.*\*",
            r'cors\(\{[^}]*origin:\s*true', r'"origin":\s*"\*"',
        ]
        if self._grep_sources("|".join(patterns)):
            return [self._issue(
                "PROD019", "HIGH", "(permissive CORS)", 0,
                "Wildcard CORS detected - restrict origins in production",
            )]
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _issue(
        self,
        rule_id: str,
        severity: str,
        file: str,
        line: int,
        message: str,
        *,
        fix_hint: str = "",
        generate_command: str = "",
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "rule_id": rule_id,
            "severity": severity,
            "file": file,
            "line": line,
            "message": message,
            "code_snippet": "",
        }
        if fix_hint:
            row["fix_hint"] = fix_hint
        if generate_command:
            row["generate_command"] = generate_command
        return row

    def _should_skip_path(self, path: Path) -> bool:
        parts = [p.lower() for p in path.parts]
        return any(part in IGNORE_DIRS for part in parts)

    def _iter_text_files(self) -> list[Path]:
        if self._text_files is not None:
            return self._text_files

        files: list[Path] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or self._should_skip_path(path):
                continue
            suffix = path.suffix.lower()
            name = path.name.lower()
            if suffix in _SOURCE_EXTENSIONS or name in _CONFIG_NAMES:
                files.append(path)
        self._text_files = files
        return files

    def _grep_sources(self, pattern: str) -> bool:
        """Return True if regex matches any scannable project file."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return False
        for path in self._iter_text_files():
            try:
                if compiled.search(path.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                continue
        return False