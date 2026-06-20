import re

from .base import Rule


class SQLInjectionRule(Rule):
    id = "SQL001"
    severity = "CRITICAL"

    PATTERNS = [
        (r'execute\([\'"]\s*SELECT.*\+', "SQL string concatenation (risk of injection)"),
        (r'execute\([\'"]\s*SELECT.*%s', "Old-style string formatting in SQL"),
        (r'execute\(f[\'"]\s*SELECT.*\{', "F-string used in SQL query"),
        (r'execute\([\'"].*\{.*\}.*[\'"]\.format\(', ".format() used in SQL query"),
        (r'query\([\'"]\s*SELECT.*\+', "SQL string concatenation in Node.js"),
        (r'query\(`[\s\S]*\$\{.*\}`', "Template literal in SQL query (risk)"),
    ]

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        full_code = "\n".join(lines)

        for pattern, desc in self.PATTERNS:
            for match in re.finditer(pattern, full_code, re.IGNORECASE):
                start_pos = match.start()
                line_no = full_code[:start_pos].count("\n") + 1
                line_start = full_code.rfind("\n", 0, start_pos) + 1
                line_end = full_code.find("\n", start_pos)
                snippet = full_code[line_start:line_end] if line_end != -1 else full_code[line_start:]
                issues.append({
                    "line": line_no,
                    "message": f"Potential SQL injection: {desc}",
                    "code_snippet": snippet.strip()
                })

        unique = {}
        for issue in issues:
            key = (issue["line"], issue["message"])
            if key not in unique:
                unique[key] = issue
        return list(unique.values())
