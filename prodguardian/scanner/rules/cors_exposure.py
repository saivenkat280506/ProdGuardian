import re

from .base import Rule


class CORSEndpointRule(Rule):
    """Detect overly permissive CORS / exposed API configurations that should not be in prod."""
    id = "API001"
    severity = "HIGH"

    PATTERNS = [
        (r'allow_origins\s*=\s*\[.*\*', "Permissive CORS: allow_origins includes '*'"),
        (r'Access-Control-Allow-Origin\s*:\s*[\'"]\*', "Permissive CORS header '*'"),
        (r'\.use\(cors\(\s*\{[^}]*origin:\s*[\'"]\*', "Express cors() with wildcard origin"),
        (r'CORS_ALLOW_ALL_ORIGINS\s*=\s*True', "Django CORS allow all origins"),
        (r'CORSMiddleware.*allow_origins.*\*', "Starlette/FastAPI CORSMiddleware with '*'"),
        (r'app\.add_middleware.*CORSMiddleware', "CORSMiddleware in use - review origins in production"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        full = "\n".join(lines)
        for pattern, desc in self.PATTERNS:
            for match in re.finditer(pattern, full, re.IGNORECASE):
                start = match.start()
                line_no = full[:start].count("\n") + 1
                snippet = full[max(0, start-20): start+80].splitlines()[0] if start else ""
                issues.append({
                    "line": line_no,
                    "message": f"API exposure risk: {desc}",
                    "code_snippet": snippet.strip()[:120],
                })
        # Dedup
        seen = set()
        out = []
        for i in issues:
            key = (i["line"], i["message"][:50])
            if key not in seen:
                seen.add(key)
                out.append(i)
        return out
