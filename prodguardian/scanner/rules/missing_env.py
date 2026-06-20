import re

from .base import Rule


class MissingEnvVarRule(Rule):
    id = "ENV001"
    severity = "HIGH"

    def check(self, ast_data):
        issues = []
        lines = ast_data["lines"]
        for i, line in enumerate(lines, start=1):
            if re.search(r'os\.getenv\(["\'][^"\']+["\']\)\s*$', line):
                issues.append(
                    {
                        "line": i,
                        "message": "Environment variable accessed without default value",
                        "code_snippet": line.strip(),
                    }
                )
            if re.search(r'os\.environ\[["\'][^"\']+["\']\]', line):
                issues.append(
                    {
                        "line": i,
                        "message": "Direct os.environ access - will raise KeyError if missing",
                        "code_snippet": line.strip(),
                    }
                )
        return issues
