# Contributing to ProdGuardian

Thank you for your interest in contributing! This guide will help you get started.

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/saivenkat280506/ProdGuardian.git
cd ProdGuardian

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

---

## Code Style

- Use **Black** for formatting: `black prodguardian/`
- Use **Ruff** for linting: `ruff check prodguardian/`
- Follow PEP 8 conventions
- Add type hints where possible
- Keep functions focused and under 50 lines

---

## Adding a New Security Rule

1. Create a new file in `prodguardian/scanner/rules/`:

```python
import re
from .base import Rule

class MyNewRule(Rule):
    id = "NEW001"
    severity = "HIGH"  # CRITICAL, HIGH, MEDIUM, LOW

    def check(self, ast_data):
        issues = []
        lines = ast_data.get("lines", [])
        for line_no, line in enumerate(lines, start=1):
            if re.search(r"dangerous_pattern", line):
                issues.append({
                    "line": line_no,
                    "message": "Description of the issue",
                    "code_snippet": line.strip()
                })
        return issues
```

2. Register the rule in `prodguardian/scanner/rule_engine.py`:

```python
from prodguardian.scanner.rules.my_new_rule import MyNewRule

ALL_RULES = [
    # ... existing rules
    MyNewRule(),
]
```

3. Add tests in `tests/test_rules.py`:

```python
class TestMyNewRule:
    def test_detects_issue(self):
        rule = MyNewRule()
        ast_data = parse_project(FIXTURES / "python_vuln" / "bad.py")
        issues = rule.check(ast_data)
        assert len(issues) > 0
```

---

## Adding a New Asset Template

1. Create a Jinja2 template in `prodguardian/production/templates/my-template.j2`

2. Add a generator function in `prodguardian/production/generator.py`:

```python
def generate_my_asset(root: Path, output_path: Optional[Path] = None) -> str:
    template = env.get_template("my-template.j2")
    content = template.render(variable="value")
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content
```

3. Add a CLI command in `prodguardian/cli.py`

4. Add tests in `tests/test_production.py`

---

## Testing Requirements

- All new features must include tests
- Maintain at least 80% code coverage
- Mock external services (LLM API calls)
- Use `pytest` for test framework

```bash
# Run with coverage
pytest tests/ --cov=prodguardian

# Run specific test file
pytest tests/test_rules.py -v
```

---

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest tests/`
6. Run linting: `ruff check .`
7. Commit with a descriptive message
8. Push to your fork
9. Create a Pull Request

---

## Reporting Issues

- Use the GitHub issue tracker
- Include steps to reproduce
- Include Python version and OS
- Include error output if applicable

---

## Code of Conduct

Please be respectful and inclusive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
