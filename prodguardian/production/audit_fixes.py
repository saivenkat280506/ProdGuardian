"""Actionable fix hints and CLI generate commands for static audit rules."""

from __future__ import annotations

from typing import Any

# Static audit focuses on existence and basic config. AI scan handles deep content review.
AUDIT_FIX_HINTS: dict[str, dict[str, str]] = {
    "PROD001": {
        "fix_hint": "Add a Dockerfile with a non-root USER and pinned base image.",
        "generate_command": "generate dockerfile",
    },
    "PROD002": {
        "fix_hint": "Add docker-compose.yml for local dev parity with production.",
        "generate_command": "generate compose",
    },
    "PROD003": {
        "fix_hint": "Add a CI workflow that runs tests on every push/PR.",
        "generate_command": "generate ci",
    },
    "PROD004": {
        "fix_hint": "Document required env vars in .env.example (no real secrets).",
        "generate_command": "generate env",
    },
    "PROD005": {
        "fix_hint": "Register a global exception/error handler so clients get safe responses.",
        "generate_command": "generate error-handler",
    },
    "PROD006": {
        "fix_hint": "Add rate limiting middleware on public API routes.",
        "generate_command": "generate rate-limiter",
    },
    "PROD009": {
        "fix_hint": (
            "Add helmet (Express) or secure-headers / Talisman (Flask) and set "
            "CSP, HSTS, and X-Frame-Options."
        ),
    },
    "PROD010": {
        "fix_hint": "Expose GET /health or /ready returning 200 for load balancer probes.",
    },
    "PROD011": {
        "fix_hint": "Switch to JSON structured logging (structlog, pino, winston json).",
    },
    "PROD012": {
        "fix_hint": (
            "Never commit .env — add `.env` to .gitignore, keep secrets in a manager "
            "(Vault, Doppler, AWS SM), and ship only .env.example."
        ),
        "generate_command": "generate env",
    },
    "PROD013": {
        "fix_hint": "Configure a connection pool (SQLAlchemy pool_size, pgBouncer, Prisma pool).",
    },
    "PROD014": {
        "fix_hint": (
            "Add an npm `build` script, set NODE_ENV=production, and disable source maps "
            "in production webpack/vite config."
        ),
    },
    "PROD015": {
        "fix_hint": "Enable OpenAPI/Swagger — FastAPI /docs or swagger-ui on /api-docs.",
    },
    "PROD016": {
        "fix_hint": "Integrate Sentry for errors and Prometheus or OpenTelemetry for metrics.",
    },
    "PROD017": {
        "fix_hint": "Document backup cadence in README and add pg_dump/mysqldump scripts.",
    },
    "PROD018": {
        "fix_hint": (
            "Add `RUN adduser` + `USER appuser` before CMD and pin images "
            "(e.g. python:3.12-slim not :latest)."
        ),
        "generate_command": "generate dockerfile",
    },
    "PROD019": {
        "fix_hint": (
            "Replace wildcard CORS with an allowlist from env, e.g. "
            "allow_origins=[os.getenv('FRONTEND_URL')] or cors({ origin: process.env.APP_URL })."
        ),
    },
}


def enrich_audit_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Attach fix_hint and optional generate_command to an audit finding."""
    meta = AUDIT_FIX_HINTS.get(issue.get("rule_id", ""), {})
    if meta.get("fix_hint"):
        issue["fix_hint"] = meta["fix_hint"]
    if meta.get("generate_command"):
        issue["generate_command"] = meta["generate_command"]
    return issue