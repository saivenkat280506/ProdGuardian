from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class SecretsAgent(BaseAgent):
    name = "SecretsAgent"

    BINARY_EXTS = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz",
        ".exe", ".dll", ".so", ".bin", ".pyc", ".pyo", ".class", ".o", ".a"
    }

    # Only scan files that commonly contain config/secrets or source
    TEXT_EXTS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".go", ".java", ".rb", ".php",
        ".env", ".ini", ".toml", ".yaml", ".yml", ".json", ".xml", ".conf", ".config",
        ".sh", ".bash", ".ps1", ".bat", ".md", ".txt", ".properties", ".gradle",
        ".Dockerfile", ""  # allow no-ext like Dockerfile, Procfile
    }

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix.lower() in self.BINARY_EXTS:
            return False
        # Allow files without suffix that are common (Dockerfile, etc) and known text exts
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        if suffix == "" and name in {"dockerfile", "procfile", "makefile", ".env", ".env.example", ".env.local"}:
            return True
        return suffix in self.TEXT_EXTS or name.startswith(".env")

    def scan(self, file_path: Path, file_content: str) -> list[dict[str, Any]]:
        # Use library for fast, in-process detection. No CLI / temp files needed.
        issues = []
        try:
            from detect_secrets import SecretsCollection
            from detect_secrets.settings import default_settings

            # Only run heavy secret scan on plausible files (reduce noise + time)
            suffix = file_path.suffix.lower()
            name = file_path.name.lower()
            if not (suffix in self.TEXT_EXTS or name.startswith(".env") or name in {"dockerfile", "procfile"}):
                return []

            with default_settings():
                sc = SecretsCollection()
                sc.scan_file(str(file_path))

                for item in list(sc):
                    if not isinstance(item, tuple) or len(item) != 2:
                        continue
                    filename, secret = item
                    # secret is PotentialSecret
                    line_no = getattr(secret, "line_number", 0)
                    secret_type = getattr(secret, "type", "Secret")
                    # Try to get a display snippet if available; fall back to short hash info
                    snippet = ""
                    try:
                        # Some versions expose secret_value (may be redacted)
                        if hasattr(secret, "secret_value") and secret.secret_value:
                            snippet = str(secret.secret_value)[:40]
                    except Exception:
                        pass
                    if not snippet:
                        snippet = f"detected:{getattr(secret, 'secret_hash', '')[:12]}"

                    issues.append({
                        "rule_id": "SECRETS001",
                        "severity": "CRITICAL",
                        "file": str(file_path),
                        "line": line_no,
                        "message": f"Secret detected: {secret_type}",
                        "code_snippet": snippet,
                    })
        except ImportError:
            # detect-secrets not available - silently skip (graceful)
            pass
        except Exception:
            # Never let secrets scanning break the whole run
            pass
        return issues
