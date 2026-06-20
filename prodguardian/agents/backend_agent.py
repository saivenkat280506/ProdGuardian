from pathlib import Path
from typing import Any

from prodguardian.cache.db import get_cached_ast, store_ast
from prodguardian.scanner.ast_parser import parse_project
from prodguardian.scanner.rule_engine import run_rules

from .base_agent import BaseAgent


class BackendAgent(BaseAgent):
    name = "BackendAgent"

    BACKEND_EXTS = {".py", ".js", ".ts", ".go", ".java", ".rb", ".php"}

    def can_handle(self, file_path: Path) -> bool:
        if file_path.suffix in {".jsx", ".tsx", ".vue"}:
            return False
        return file_path.suffix in self.BACKEND_EXTS

    def scan(self, file_path: Path, file_content: str) -> list[dict[str, Any]]:
        cached = get_cached_ast(file_path)
        if cached:
            return cached.get("issues", [])

        ast_data = parse_project(file_path)
        if ast_data is None:
            return []
        issues = run_rules(ast_data)
        store_ast(file_path, {"issues": issues})
        return issues
