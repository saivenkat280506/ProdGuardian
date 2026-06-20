import re

from .base import Rule


class HardcodedSecretsRule(Rule):
    id = "SEC001"
    severity = "CRITICAL"

    PATTERNS = [
        (r'["\']?api_key["\']?\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']', "API key"),
        (r'["\']?password["\']?\s*[:=]\s*["\'][^"\']{4,}["\']', "Password"),
        (r'["\']?secret["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Secret token"),
        (r"sk-[A-Za-z0-9]{20,}", "OpenAI API key"),
        (r"ghp_[A-Za-z0-9]{36}", "GitHub token"),
        (r'["\']?secret_key["\']?\s*[:=]\s*["\'][^"\']{8,}["\']', "Secret key"),
        (r'["\']?access_token["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Access token"),
        (r'["\']?private_key["\']?\s*[:=]\s*["\'][^"\']{10,}["\']', "Private key"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data["lines"]
        for line_no, line in enumerate(lines, start=1):
            for pattern, desc in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(
                        {
                            "line": line_no,
                            "message": f"Hardcoded {desc} found",
                            "code_snippet": line.strip(),
                        }
                    )
                    break
        return issues
