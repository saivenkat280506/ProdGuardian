import re

from .base import Rule


class ProdLeakageRule(Rule):
    """Catch common things left in code that should never ship to production."""
    id = "LEAK001"
    severity = "HIGH"

    PATTERNS = [
        # Python debug / breakpoints
        (r'\bpdb\.set_trace\b', "pdb.set_trace() left in code"),
        (r'\bbreakpoint\s*\(', "breakpoint() left in code"),
        (r'__import__\([\'"]pdb[\'"]\)', "Dynamic pdb import"),
        # JS debug
        (r'\bdebugger\s*;', "debugger; statement left in JS"),
        (r'console\.(log|debug|info)\s*\([^)]*(password|secret|token|api[_-]?key|private)', "Console logging sensitive value"),
        # Logging sensitive data
        (r'(print|logger\.|logging\.|log\.)\s*\([^)]*(password|secret|api[_-]?key|private_key|access_token)\s*[,\)]', "Potential logging of secrets/credentials"),
        (r'print\s*\(\s*os\.environ', "Printing whole environment (may leak secrets)"),
        # Common prod-unready
        (r'#\s*(TODO|FIXME|HACK|REMOVE)\s*.*(prod|production|secret|key|password|before deploy)', "TODO/FIXME referencing secrets or prod cleanup"),
        (r'raise\s+NotImplementedError.*(prod|production)', "NotImplemented left for prod path"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        for i, line in enumerate(lines, start=1):
            for pattern, desc in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": i,
                        "message": f"Production leakage: {desc}",
                        "code_snippet": line.strip()[:140],
                    })
                    break  # one issue per line
        return issues
