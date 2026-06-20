import re
from pathlib import Path
from typing import Optional


def detect_framework(root: Path) -> dict[str, Optional[str]]:
    """
    Returns dict with:
    - 'type': 'python' or 'node' or 'unknown'
    - 'web_framework': 'flask'/'fastapi'/'django'/'express' or None
    - 'package_manager': 'pip'/'npm'/'yarn'
    """
    result = {"type": "unknown", "web_framework": None, "package_manager": None}

    # Python detection
    if (
        (root / "requirements.txt").exists()
        or (root / "setup.py").exists()
        or (root / "pyproject.toml").exists()
    ):
        result["type"] = "python"
        result["package_manager"] = "pip"
        for file in root.rglob("*.py"):
            try:
                content = file.read_text(encoding="utf-8")
                if re.search(r"from\s+flask\s+import|import\s+flask", content, re.IGNORECASE):
                    result["web_framework"] = "flask"
                    break
                if re.search(r"from\s+fastapi\s+import|import\s+fastapi", content, re.IGNORECASE):
                    result["web_framework"] = "fastapi"
                    break
                if re.search(r"from\s+django|import\s+django", content, re.IGNORECASE):
                    result["web_framework"] = "django"
                    break
            except Exception:
                pass

    # Node.js detection
    elif (root / "package.json").exists():
        result["type"] = "node"
        result["package_manager"] = "npm"
        try:
            pkg = (root / "package.json").read_text(encoding="utf-8")
            if '"express"' in pkg:
                result["web_framework"] = "express"
            elif '"next"' in pkg:
                result["web_framework"] = "nextjs"
        except Exception:
            pass

    return result
