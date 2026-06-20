import re

from .base import Rule


class DebugEndpointsRule(Rule):
    id = "DEV001"
    severity = "HIGH"

    PATTERNS = [
        (r'@app\.route\([\'"]/debug', "Flask debug endpoint"),
        (r'\.get\([\'"]/debug', "Express/FastAPI debug endpoint"),
        (r'@router\.(get|post)\([\'"]/debug', "FastAPI router debug endpoint"),
        (r'debug=True', "Debug mode enabled"),
        (r'app\.run\(.*debug=True', "Flask debug mode"),
        (r'uvicorn\.run\(.*reload=True', "Uvicorn auto-reload enabled"),
        (r'\["debug"\]\s*=\s*True', "Debug flag in config"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        for line_no, line in enumerate(lines, start=1):
            for pattern, desc in self.PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": line_no,
                        "message": f"Exposed debug/development route or flag: {desc}",
                        "code_snippet": line.strip()
                    })
                    break
        return issues
