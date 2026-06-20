import re
from pathlib import Path
from typing import Any

from .base_agent import BaseAgent


class FrontendAgent(BaseAgent):
    name = "FrontendAgent"

    EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".vue"}

    PATTERNS = [
        (r'dangerouslySetInnerHTML', "dangerouslySetInnerHTML - XSS risk"),
        (r'innerHTML\s*=', "Direct innerHTML assignment - XSS risk"),
        (r'v-html\s*=', "v-html directive - XSS risk (Vue)"),
        (r'eval\s*\(', "Use of eval() in frontend code"),
        (r'localStorage\.setItem', "Storing sensitive data in localStorage"),
        (r'sessionStorage\.setItem', "Storing sensitive data in sessionStorage"),
        (r'fetch\(["\'][^"\']*localhost', "Hardcoded localhost API URL"),
    ]

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix in self.EXTENSIONS

    def scan(self, file_path: Path, file_content: str) -> list[dict[str, Any]]:
        issues = []
        lines = file_content.splitlines()
        for i, line in enumerate(lines, start=1):
            for pattern, msg in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "rule_id": "FRONT001",
                        "severity": "HIGH",
                        "file": str(file_path),
                        "line": i,
                        "message": msg,
                        "code_snippet": line.strip(),
                    })
                    break
        return issues
