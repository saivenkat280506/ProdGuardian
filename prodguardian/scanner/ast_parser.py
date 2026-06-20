from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjs.language())


def get_parser_for_file(filepath: Path):
    if filepath.suffix == ".py":
        parser = Parser(PY_LANGUAGE)
    elif filepath.suffix in [".js", ".ts", ".jsx", ".tsx"]:
        parser = Parser(JS_LANGUAGE)
    else:
        return None
    return parser


def parse_project(filepath: Path):
    parser = get_parser_for_file(filepath)
    if not parser:
        return None
    with open(filepath, "rb") as f:
        code = f.read()
    tree = parser.parse(code)
    return {
        "path": str(filepath),
        "tree": tree,
        "code": code.decode("utf-8", errors="ignore"),
        "lines": code.decode().splitlines(),
    }
