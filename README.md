# ProdGuardian

[![PyPI version](https://badge.fury.io/py/prodguardian.svg)](https://pypi.org/project/prodguardian/)
[![Tests](https://github.com/yourusername/prodguardian/actions/workflows/test.yml/badge.svg)](https://github.com/yourusername/prodguardian/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Production readiness auditor for vibe-coded apps**

ProdGuardian scans your codebase for security issues, checks for missing production assets (Dockerfile, CI/CD, env config), and generates them automatically. Bring your own API key for AI-powered fix suggestions.

---

## Features

- **Parallel Agent Analysis** - Multiple specialized agents (Secrets, Backend, Frontend) running in parallel processes + AST + entropy secret detection + production leakage & API exposure rules
- **Production Readiness Audit** - Detects missing Dockerfiles, CI pipelines, env configs, error handlers
- **Asset Generation** - Creates Dockerfiles, GitHub Actions CI, docker-compose.yml, .env.example, error handlers, rate limiters
- **LLM-Powered Fixes** - Get AI explanations and fix suggestions (bring your own API key)
- **Framework Detection** - Automatically detects Flask, FastAPI, Django, Express, Next.js
- **Cost Safety** - Token budgeting and cost estimation before LLM calls
- **Caching** - SQLite cache for faster subsequent scans

---

## Quick Start

```bash
# Install
pip install prodguardian

# Scan for security issues
prodguardian scan .

# Check for missing production assets
prodguardian audit .

# Generate missing assets
prodguardian generate dockerfile
prodguardian generate ci
prodguardian generate env
```

---

## Commands

| Command | Description |
|---------|-------------|
| `prodguardian scan [PATH]` | Scan codebase for security issues |
| `prodguardian audit [PATH]` | Check for missing production assets |
| `prodguardian generate dockerfile` | Generate a Dockerfile |
| `prodguardian generate ci` | Generate GitHub Actions CI workflow |
| `prodguardian generate env` | Generate .env.example from code |
| `prodguardian generate compose` | Generate docker-compose.yml |
| `prodguardian generate error-handler` | Generate error handler middleware |
| `prodguardian generate rate-limiter` | Generate rate limiter middleware |
| `prodguardian explain ISSUE_ID` | Explain an issue (requires API key) |
| `prodguardian fix ISSUE_ID` | Generate a fix (requires API key) |

---

## Security Rules

| Rule ID | Severity | Description |
|---------|----------|-------------|
| SEC001 | CRITICAL | Hardcoded secrets (API keys, passwords) via advanced detector |
| ENV001 | HIGH | Missing environment variable defaults |
| DEV001 | HIGH | Debug endpoints / flags exposed |
| SQL001 | CRITICAL | SQL injection vulnerabilities |
| EXEC001 | CRITICAL | Unsafe eval/exec usage |
| API001 | HIGH | Permissive CORS / overly exposed API (e.g. allow_origins="*") |
| LEAK001 | HIGH | Production leakage (pdb, breakpoint, secret logging, TODOs with secrets, console sensitive logs) |
| FRONT001 | HIGH | Frontend XSS risks (dangerouslySetInnerHTML, innerHTML) |

---

## Configuration

ProdGuardian stores user settings in `~/.prodguardian.toml` (created automatically
when you use the TUI Settings screen). You can also copy `.env.example` to `.env`
for environment-variable overrides.

### Config file (`~/.prodguardian.toml`)

```toml
[llm]
provider = "api"
model = "groq/llama-3.1-8b-instant"
api_key = "your-api-key-here"
base_url = ""
max_cost_usd = 0.10
max_tokens = 32000
scan_mode = "mono"          # mono | hybrid
analyzer_model = "groq/llama-3.3-70b-versatile"
reporter_model = "groq/llama-3.1-8b-instant"

[scan]
parallel = true
workers = 4
ignore_dirs = [".git", "node_modules", ".venv"]
groq_chunk_delay = 6

[generator]
auto_confirm = false
```

For Ollama, set `model = "ollama/llama3.2:3b"` and leave `api_key` empty (local
daemon is used automatically).

### Environment overrides (optional)

These override values from `~/.prodguardian.toml` at runtime:

```bash
export PRODGUARDIAN_API_KEY=gsk_...
export PRODGUARDIAN_MODEL=groq/llama-3.1-8b-instant
export PRODGUARDIAN_BASE_URL=
export PRODGUARDIAN_SCAN_MODE=mono
export PRODGUARDIAN_ANALYZER_MODEL=groq/llama-3.3-70b-versatile
export PRODGUARDIAN_REPORTER_MODEL=groq/llama-3.1-8b-instant
```

See `.env.example` for the full list with placeholders.

---

## LLM Integration

Configure your API key in `~/.prodguardian.toml` (recommended) or via
`PRODGUARDIAN_API_KEY`. The model prefix selects the provider (`groq/…`,
`openai/…`, `anthropic/…`, `ollama/…`).

Then use:

```bash
prodguardian explain SEC001:app.py:42
prodguardian fix SEC001:app.py:42 --yes
```

---

## Comparison

| Feature | ProdGuardian | Semgrep | Canopy | Vibeguard |
|---------|-------------|---------|--------|-----------|
| AST-based scanning | ✅ | ✅ | ❌ | ❌ |
| Asset generation | ✅ | ❌ | ❌ | ❌ |
| LLM-powered fixes | ✅ | ❌ | ❌ | ✅ |
| Framework detection | ✅ | ❌ | ❌ | ❌ |
| Cost safety | ✅ | N/A | N/A | ❌ |
| Offline mode | ✅ | ✅ | ✅ | ❌ |

---

## Development

```bash
# Clone
git clone https://github.com/yourusername/prodguardian.git
cd prodguardian

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linting
ruff check .
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - see [LICENSE](LICENSE) for details.
