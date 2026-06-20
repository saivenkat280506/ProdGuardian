"""Built-in preset and rule templates for vibe-coded production checks.

Presets are keyword/pattern lists used by:
- ``CodebaseLLMScanner`` (injected into mono/hybrid LLM prompts)
- ``scan_file_presets`` (fast static keyword pass)

Each preset supports:
- ``name``, ``description``, ``items`` (keywords), optional ``patterns`` (regex-oriented strings)
- ``severity``: CRITICAL | HIGH | MEDIUM | LOW
- ``category``: grouping for UI and LLM context
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PRESET_CATEGORIES: tuple[str, ...] = (
    "Secrets & Credentials",
    "Debug & Development Code",
    "Production Leakage",
    "Security Vulnerabilities",
    "Frontend Security",
    "Infrastructure & Docker Security",
    "CI/CD Security Issues",
    "Poor Logging & Error Handling",
    "AI-Generated Code Anti-Patterns",
    "Dependency & Supply Chain Risks",
)

VALID_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})

BUILTIN_PRESET_TEMPLATES: list[dict[str, Any]] = [
    # --- Secrets & Credentials ---
    {
        "id": "tpl_secrets",
        "name": "Hardcoded Secrets",
        "description": "API keys, tokens, and passwords embedded in source or config files.",
        "items": [
            "sk-", "api_key=", "API_KEY=", "password=", "SECRET_KEY", "token=", "Bearer ",
            "PRIVATE_KEY", "aws_secret", "client_secret", "DATABASE_URL=postgres://",
        ],
        "category": "Secrets & Credentials",
        "severity": "CRITICAL",
        "recommended": True,
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_cloud_credentials",
        "name": "Cloud & Service Credentials",
        "description": "Cloud provider keys and third-party service credentials in code.",
        "items": [
            "AKIA", "ASIA", "ghp_", "gho_", "xoxb-", "xoxp-", "AIza", "firebase",
            "TWILIO_", "SENDGRID_", "STRIPE_SK", "STRIPE_SECRET", "OPENAI_API_KEY=",
            "ANTHROPIC_API_KEY", "GROQ_API_KEY", "HUGGINGFACE_", "AZURE_CLIENT_SECRET",
        ],
        "category": "Secrets & Credentials",
        "severity": "CRITICAL",
        "recommended": True,
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_client_secrets",
        "name": "Client-Side Exposed Secrets",
        "description": "Secrets or private keys shipped to browser bundles or public env vars.",
        "items": [
            "NEXT_PUBLIC_SECRET", "VITE_SECRET", "REACT_APP_SECRET", "localStorage.setItem",
            "sessionStorage.setItem", "document.cookie", "privateKey", "service_role",
            "dangerouslySetInnerHTML", "REACT_APP_API_KEY", "NEXT_PUBLIC_API_KEY",
        ],
        "category": "Frontend Security",
        "severity": "CRITICAL",
        "builtin": True,
        "enabled": True,
    },
    # --- Debug & Development Code ---
    {
        "id": "tpl_debug",
        "name": "Debug Code",
        "description": "Debug logging, breakpoints, and development-only statements.",
        "items": [
            "console.log", "console.debug", "console.warn", "debugger", "pdb.set_trace",
            "breakpoint(", "print(", "alert(", "import ipdb", "debug=True", "DEBUG = True",
        ],
        "category": "Debug & Development Code",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_dev_packages",
        "name": "Dev Packages",
        "description": "Development-only packages listed as production dependencies.",
        "items": [
            "faker", "pytest", "nodemon", "webpack-dev-server", "hot-reload", "storybook",
            "jest", "@testing-library", "supertest", "morgan", "http-proxy-middleware",
        ],
        "category": "Debug & Development Code",
        "severity": "MEDIUM",
        "builtin": True,
        "enabled": True,
    },
    # --- Production Leakage ---
    {
        "id": "tpl_localhost",
        "name": "Local / Dev URLs",
        "description": "Hardcoded localhost, private IPs, or tunnel URLs in production paths.",
        "items": [
            "localhost", "127.0.0.1", "0.0.0.0", "ngrok.io", "192.168.", "10.0.",
            "trycloudflare.com", "localstack", "host.docker.internal",
        ],
        "category": "Production Leakage",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_vibe_markers",
        "name": "Vibe Markers",
        "description": "Temporary comments and markers left by AI-assisted coding sessions.",
        "items": [
            "TODO: remove", "FIXME", "HACK", "vibe-coded", "temp fix", "remove before prod",
            "AI generated", "chatgpt", "copilot", "do not ship", "WIP", "XXX",
        ],
        "category": "AI-Generated Code Anti-Patterns",
        "severity": "MEDIUM",
        "builtin": True,
        "enabled": True,
    },
    # --- Security Vulnerabilities ---
    {
        "id": "tpl_sql_injection",
        "name": "SQL Injection Patterns",
        "description": "Unsafe SQL built via string concatenation or f-strings.",
        "items": [
            "execute(f\"", "execute(f'", "execute(\"SELECT", "execute('SELECT",
            "rawQuery", "cursor.execute(", "+ sql", "format(sql", ".query(`SELECT",
            "f\"SELECT", "f'SELECT", "execute(%", "string.Format(\"SELECT",
        ],
        "category": "Security Vulnerabilities",
        "severity": "CRITICAL",
        "recommended": True,
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_command_injection",
        "name": "Command Injection",
        "description": "Shell commands built from user input or unsafe subprocess usage.",
        "items": [
            "os.system(", "subprocess.call(", "shell=True", "exec(", "eval(",
            "child_process.exec", "spawn(", "popen(", "Runtime.getRuntime().exec",
        ],
        "category": "Security Vulnerabilities",
        "severity": "CRITICAL",
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_ssrf",
        "name": "SSRF Patterns",
        "description": "Server-side requests to user-controlled or internal URLs.",
        "items": [
            "requests.get(url", "fetch(userUrl", "axios.get(req", "urllib.request.urlopen",
            "http.get(params", "got(url", "file://", "gopher://", "metadata.google",
            "169.254.169.254",
        ],
        "category": "Security Vulnerabilities",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_path_traversal",
        "name": "Path Traversal",
        "description": "File paths assembled from user input without sanitization.",
        "items": [
            "../", "..\\", "path.join(req", "os.path.join(user", "send_file(request",
            "readFile(userInput", "open(params", "File(path", "fs.readFileSync(req",
        ],
        "category": "Security Vulnerabilities",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    # --- Frontend Security ---
    {
        "id": "tpl_xss",
        "name": "XSS & Unsafe DOM",
        "description": "Cross-site scripting via unsafe HTML injection or innerHTML.",
        "items": [
            "innerHTML", "outerHTML", "document.write", "v-html", "dangerouslySetInnerHTML",
            "insertAdjacentHTML", "__html:", "eval(", "new Function(", "setTimeout(\"",
        ],
        "category": "Frontend Security",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    # --- Infrastructure & Docker ---
    {
        "id": "tpl_docker_insecure",
        "name": "Docker & Infrastructure Risks",
        "description": (
            "Deep scan: privileged containers, weak compose secrets, cap_add. "
            "(Dockerfile USER/:latest is checked by static Audit.)"
        ),
        "items": [
            "privileged: true", "privileged=true", "--privileged",
            "network_mode: host", "cap_add:", "chmod 777",
            "password: admin", "MYSQL_ROOT_PASSWORD=root", "ENV PASSWORD",
        ],
        "category": "Infrastructure & Docker Security",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    # --- CI/CD ---
    {
        "id": "tpl_cicd_security",
        "name": "CI/CD Security Issues",
        "description": "Secrets and unsafe practices in CI/CD pipeline definitions.",
        "items": [
            "secrets.", "echo $", "printenv", "env:", "curl -H", "password:",
            "token:", "api-key:", "insecure-skip-tls", "continue-on-error: true",
            "pull_request_target", "GITHUB_TOKEN",
        ],
        "category": "CI/CD Security Issues",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    # --- Logging & Errors ---
    {
        "id": "tpl_logging_errors",
        "name": "Poor Logging & Error Handling",
        "description": "Leaky error responses, stack traces, or missing structured logging.",
        "items": [
            "traceback.print_exc", "console.error(err)", "res.send(err)", "str(e)",
            "detail=str(exc)", "include_stacktrace", "debug=True", "app.debug",
            "print(exception", "logger.exception", "pass  # ignore",
        ],
        "category": "Poor Logging & Error Handling",
        "severity": "MEDIUM",
        "builtin": True,
        "enabled": True,
    },
    # --- AI Anti-Patterns ---
    {
        "id": "tpl_ai_antipatterns",
        "name": "AI-Generated Anti-Patterns",
        "description": (
            "Common unsafe patterns from LLM-assisted coding: disabled TLS, mock auth, "
            "hardcoded credentials. (Obvious wildcard CORS also flagged by static Audit.)"
        ),
        "items": [
            "verify=False", "ssl=False", "disable_ssl", "rejectUnauthorized: false",
            "NODE_TLS_REJECT_UNAUTHORIZED", "mock auth", "skip authentication",
            "hardcoded user", "admin/admin", "# TODO: security",
        ],
        "recommended": True,
        "category": "AI-Generated Code Anti-Patterns",
        "severity": "HIGH",
        "builtin": True,
        "enabled": True,
    },
    # --- Supply Chain ---
    {
        "id": "tpl_supply_chain",
        "name": "Dependency & Supply Chain Risks",
        "description": "Unpinned deps, install scripts, and risky package sources.",
        "items": [
            "npm install http://", "pip install git+", "postinstall", "preinstall",
            "curl | bash", "wget | sh", "requirements.txt", "*", "latest",
            "yarn add github:", "pip install --user", "npx --yes",
        ],
        "category": "Dependency & Supply Chain Risks",
        "severity": "MEDIUM",
        "builtin": True,
        "enabled": True,
    },
]

BUILTIN_RULE_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "tpl_rule_secrets",
        "name": "No hardcoded secrets",
        "instruction": (
            "Search for Hardcoded Secrets and Cloud & Service Credentials presets. "
            "Flag API keys, tokens, database URLs with passwords, and cloud credentials "
            "that must use environment variables or a secrets manager. Include file path "
            "and line number for each finding."
        ),
        "preset_names": ["Hardcoded Secrets", "Cloud & Service Credentials"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_client_secrets",
        "name": "No client-side secrets",
        "instruction": (
            "Apply Client-Side Exposed Secrets preset. Flag any secret, service role key, "
            "or private credential referenced in frontend code, NEXT_PUBLIC_/VITE_/REACT_APP_ "
            "env vars, or browser storage. Suggest server-side proxy patterns."
        ),
        "preset_names": ["Client-Side Exposed Secrets"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_debug",
        "name": "No debug statements",
        "instruction": (
            "Search for Debug Code presets in API handlers, middleware, and production bundles. "
            "Flag console logging, breakpoints, debug prints, and DEBUG=True in shipped code."
        ),
        "preset_names": ["Debug Code"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_localhost",
        "name": "No local endpoints",
        "instruction": (
            "Search Local / Dev URLs presets in API routes, fetch/axios calls, WebSocket URLs, "
            "and config defaults. Production code must use environment-based hostnames."
        ),
        "preset_names": ["Local / Dev URLs"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_dev_deps",
        "name": "No dev packages in prod",
        "instruction": (
            "Inspect package.json dependencies, requirements.txt, pyproject.toml, and lockfiles "
            "for Dev Packages presets listed outside devDependencies or optional groups."
        ),
        "preset_names": ["Dev Packages"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_sqli",
        "name": "SQL injection prevention",
        "instruction": (
            "Apply SQL Injection Patterns preset. Flag dynamic SQL built with f-strings, "
            "concatenation, or unsanitized user input. Recommend parameterized queries or ORM "
            "bindings with concrete examples from the codebase."
        ),
        "preset_names": ["SQL Injection Patterns"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_cmd_injection",
        "name": "Command injection prevention",
        "instruction": (
            "Apply Command Injection preset. Flag os.system, subprocess with shell=True, "
            "eval/exec, and shell command strings built from request data."
        ),
        "preset_names": ["Command Injection"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_ssrf",
        "name": "SSRF prevention",
        "instruction": (
            "Apply SSRF Patterns preset. Flag outbound HTTP calls using user-supplied URLs, "
            "metadata endpoints, or file:// handlers without allowlists."
        ),
        "preset_names": ["SSRF Patterns"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_path_traversal",
        "name": "Path traversal prevention",
        "instruction": (
            "Apply Path Traversal preset. Flag file read/write paths built from user input "
            "without normalization, chroot, or allowlist checks."
        ),
        "preset_names": ["Path Traversal"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_xss",
        "name": "XSS prevention",
        "instruction": (
            "Apply XSS & Unsafe DOM preset in frontend templates and API responses returning HTML. "
            "Flag innerHTML, dangerouslySetInnerHTML, v-html, and unsanitized user content."
        ),
        "preset_names": ["XSS & Unsafe DOM"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_docker",
        "name": "Docker security hardening",
        "instruction": (
            "Apply Docker & Infrastructure Risks preset in Dockerfile, compose files, and K8s "
            "manifests. Flag root users, privileged mode, weak default passwords, and :latest tags."
        ),
        "preset_names": ["Docker & Infrastructure Risks"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_cicd",
        "name": "CI/CD secret safety",
        "instruction": (
            "Apply CI/CD Security Issues preset in GitHub Actions, GitLab CI, and Jenkins files. "
            "Flag plaintext secrets, echoing env vars, pull_request_target misuse, and skipped gates."
        ),
        "preset_names": ["CI/CD Security Issues"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_logging",
        "name": "Production logging standards",
        "instruction": (
            "Apply Poor Logging & Error Handling preset. Flag stack traces returned to clients, "
            "raw exception strings in API responses, and missing structured logging in services."
        ),
        "preset_names": ["Poor Logging & Error Handling"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_vibe",
        "name": "No vibe markers shipped",
        "instruction": (
            "Search Vibe Markers and AI-Generated Anti-Patterns presets. Flag TODO/FIXME/HACK "
            "comments, disabled auth, verify=False, and wildcard CORS left in production paths."
        ),
        "preset_names": ["Vibe Markers", "AI-Generated Anti-Patterns"],
        "builtin": True,
        "enabled": True,
    },
    {
        "id": "tpl_rule_supply_chain",
        "name": "Supply chain hygiene",
        "instruction": (
            "Apply Dependency & Supply Chain Risks preset. Flag unpinned versions, install-from-URL "
            "patterns, curl|bash bootstrap scripts, and lifecycle scripts with network side effects."
        ),
        "preset_names": ["Dependency & Supply Chain Risks"],
        "builtin": True,
        "enabled": True,
    },
]


def get_preset_keywords(preset: dict[str, Any]) -> list[str]:
    """Return all keyword/pattern strings for matching (backward compatible)."""
    keywords: list[str] = []
    for key in ("items", "patterns"):
        for raw in preset.get(key, []):
            text = str(raw).strip()
            if text:
                keywords.append(text)
    return keywords


def normalize_preset(preset: dict[str, Any]) -> dict[str, Any]:
    """Ensure optional fields have safe defaults."""
    row = deepcopy(preset)
    severity = str(row.get("severity", "HIGH")).upper()
    if severity not in VALID_SEVERITIES:
        severity = "HIGH"
    row["severity"] = severity
    row.setdefault("category", "General")
    row.setdefault("description", "")
    row.setdefault("items", [])
    row.setdefault("patterns", [])
    row.setdefault("enabled", True)
    return row


def merge_builtin_items(
    saved_items: list[dict[str, Any]],
    builtins: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep built-in templates updated while preserving user edits and custom rows."""
    saved_by_id = {item.get("id"): item for item in saved_items if item.get("id")}
    custom = [item for item in saved_items if not item.get("builtin")]
    merged: list[dict[str, Any]] = []

    for template in builtins:
        tpl_id = template["id"]
        if tpl_id in saved_by_id:
            row = deepcopy(saved_by_id[tpl_id])
            row["builtin"] = True
            merged.append(normalize_preset(row))
        else:
            merged.append(normalize_preset(template))

    seen_custom_ids: set[str] = set()
    for item in custom:
        item_id = item.get("id") or ""
        if item_id in seen_custom_ids:
            continue
        seen_custom_ids.add(item_id)
        merged.append(normalize_preset(item))
    return merged


def load_all_presets(user_presets: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Load built-in presets merged with optional user-defined presets."""
    if not user_presets:
        return [normalize_preset(p) for p in deepcopy(BUILTIN_PRESET_TEMPLATES)]
    return merge_builtin_items(user_presets, BUILTIN_PRESET_TEMPLATES)


def load_all_rules(user_rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Load built-in LLM rules merged with optional user-defined rules."""
    if not user_rules:
        return deepcopy(BUILTIN_RULE_TEMPLATES)
    return merge_builtin_items(user_rules, BUILTIN_RULE_TEMPLATES)


def format_preset_for_llm(preset: dict[str, Any]) -> str:
    """Single-preset line for mono/hybrid LLM prompts."""
    keywords = ", ".join(get_preset_keywords(preset))
    rec = " [Recommended for Production]" if preset.get("recommended") else ""
    parts = [
        f"  - [{preset.get('severity', 'HIGH')}] {preset.get('name', 'Preset')}{rec}",
        f"    Category: {preset.get('category', 'General')}",
    ]
    if preset.get("description"):
        parts.append(f"    Description: {preset['description']}")
    parts.append(f"    Keywords/patterns: {keywords}")
    parts.append(
        "    Action: cite exact file:line, matched pattern, and a one-line remediation."
    )
    return "\n".join(parts)


def format_rule_for_llm(rule: dict[str, Any]) -> str:
    """Single-rule block with detailed hybrid-mode context."""
    linked = ", ".join(rule.get("preset_names", [])) or "all presets"
    hybrid_note = rule.get("hybrid_hint", (
        "Analyzer: bullet points as `file:line — finding`. "
        "Reporter: emit JSON only, one object per confirmed issue."
    ))
    return (
        f"  - {rule.get('name', 'Rule')}\n"
        f"    Instruction: {rule.get('instruction', '')}\n"
        f"    Linked presets: {linked}\n"
        f"    Hybrid mode: {hybrid_note}"
    )


def build_llm_presets_context(
    presets: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    *,
    compact: bool = False,
) -> str:
    """Rich presets + rules block grouped by category for mono and hybrid scan modes."""
    enabled_presets = [normalize_preset(p) for p in presets if p.get("enabled", True)]
    enabled_rules = [r for r in rules if r.get("enabled", True)]
    if not enabled_presets and not enabled_rules:
        return ""

    if compact:
        preset_lines = []
        for preset in enabled_presets[:24]:
            keywords = ", ".join(get_preset_keywords(preset)[:6])
            preset_lines.append(
                f"  - [{preset.get('severity', 'HIGH')}] {preset.get('name', 'Preset')}: {keywords}"
            )
        rule_lines = [
            f"  - {rule.get('name', 'Rule')}: {rule.get('instruction', '')[:120]}"
            for rule in enabled_rules[:12]
        ]
        return "\n".join(
            [
                "=== Guardrails (compact) ===",
                "Presets:",
                *preset_lines,
                "Rules:",
                *rule_lines,
                "Return ONLY a JSON array of findings.",
            ]
        )

    parts = [
        "=== Production Guardrails (user presets + scan rules) ===",
        "",
        "Presets — keywords/patterns that must NOT appear in production code:",
    ]

    by_category: dict[str, list[dict[str, Any]]] = {cat: [] for cat in PRESET_CATEGORIES}
    for preset in enabled_presets:
        cat = preset.get("category", "General")
        by_category.setdefault(cat, []).append(preset)

    for category in PRESET_CATEGORIES:
        group = by_category.get(category, [])
        if not group:
            continue
        parts.append(f"\n[{category}]")
        for preset in group:
            parts.append(format_preset_for_llm(preset))

    if enabled_rules:
        parts.append("\nScan rules — apply these checks using the presets above:")
        for rule in enabled_rules:
            parts.append(format_rule_for_llm(rule))

    parts.append(
        "\nOutput contract (mono + hybrid reporter):"
        "\n- Return ONLY a JSON array — no markdown fences, no prose."
        "\n- Each item: rule_id (LLM001), severity, file (relative path), line, message, code_snippet."
        "\n- Skip findings already covered by static Audit (missing Dockerfile, README, etc.)."
        "\n- Focus on code-level leaks and vulnerabilities visible in the files provided."
    )
    return "\n".join(parts)