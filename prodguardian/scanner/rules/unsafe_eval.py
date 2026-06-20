import re

from .base import Rule


class UnsafeEvalRule(Rule):
    id = "EXEC001"
    severity = "CRITICAL"

    PATTERNS = [
        (r'\beval\s*\(', "Use of eval() - arbitrary code execution risk"),
        (r'\bexec\s*\(', "Use of exec() - arbitrary code execution risk"),
        (r'Function\([\'"].*[\'"]\)', "Dynamic Function constructor (JS)"),
        (r'setTimeout\([\'"]', "setTimeout with string code (JS)"),
        (r'setInterval\([\'"]', "setInterval with string code (JS)"),
        (r'__import__\([\'"]', "Dynamic __import__ (Python)"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        for line_no, line in enumerate(lines, start=1):
            for pattern, desc in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": line_no,
                        "message": f"Unsafe dynamic code execution: {desc}",
                        "code_snippet": line.strip()
                    })
                    break
        return issues
