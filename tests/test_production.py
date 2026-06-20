import pytest
import tempfile
from pathlib import Path
from prodguardian.production.auditor import ProductionAuditor
from prodguardian.production.generator import (
    generate_dockerfile,
    generate_github_ci,
    generate_env_example,
    generate_docker_compose,
    generate_error_handler,
    generate_rate_limiter,
)
from prodguardian.utils.framework_detect import detect_framework

FIXTURES = Path(__file__).parent / "fixtures"


class TestFrameworkDetection:
    def test_detect_python_project(self):
        info = detect_framework(FIXTURES / "python_vuln")
        assert info["type"] == "python"
        assert info["package_manager"] == "pip"

    def detect_flask_framework(self):
        info = detect_framework(FIXTURES / "mixed_repo" / "backend")
        assert info["type"] == "python"
        assert info["web_framework"] == "flask"

    def test_detect_unknown_project(self):
        info = detect_framework(FIXTURES / "mixed_repo" / "config")
        assert info["type"] == "unknown"


class TestProductionAuditor:
    def test_audit_missing_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("print('hello')")
            auditor = ProductionAuditor(root)
            issues = auditor.audit()
            rule_ids = [i["rule_id"] for i in issues]
            assert "PROD001" in rule_ids
            assert "PROD003" in rule_ids
            assert "PROD004" in rule_ids
            assert "PROD007" in rule_ids
            assert "PROD008" in rule_ids

    def test_audit_complete_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "Dockerfile").write_text(
                "FROM python:3.12-slim\nWORKDIR /app\nUSER appuser\nCOPY . .\n"
            )
            (root / "docker-compose.yml").touch()
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").touch()
            (root / ".env.example").touch()
            (root / "README.md").write_text("## Backup\nNightly pg_dump snapshots.\n")
            (root / ".gitignore").write_text(".env\n*.env\n")
            auditor = ProductionAuditor(root)
            issues = auditor.audit()
            rule_ids = {i["rule_id"] for i in issues}
            assert "PROD001" not in rule_ids
            assert "PROD003" not in rule_ids

    def test_audit_new_static_rules_triggered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "requirements.txt").write_text("flask\n")
            (root / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
            auditor = ProductionAuditor(root)
            issues = auditor.audit()
            rule_ids = [i["rule_id"] for i in issues]
            assert "PROD009" in rule_ids
            assert "PROD010" in rule_ids
            assert "PROD005" in rule_ids


class TestGenerator:
    def test_generate_dockerfile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "requirements.txt").write_text("flask\n")
            (root / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
            content = generate_dockerfile(root)
            assert "flask" in content.lower() or "python" in content.lower()

    def test_generate_github_ci(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = generate_github_ci(root)
            assert "CI" in content or "ci" in content
            assert "pytest" in content or "test" in content

    def test_generate_env_example(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text('import os\nDB = os.getenv("DATABASE_URL")\n')
            content = generate_env_example(root)
            assert "DATABASE_URL" in content

    def test_generate_docker_compose(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            content = generate_docker_compose(root)
            assert "services" in content or "app" in content

    def test_generate_error_handler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("from flask import Flask\n")
            content = generate_error_handler(root)
            assert "errorhandler" in content or "error" in content.lower()

    def test_generate_rate_limiter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("from flask import Flask\n")
            content = generate_rate_limiter(root)
            assert "limiter" in content.lower() or "rate" in content.lower()

    def test_generate_dockerfile_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out = root / "Dockerfile"
            generate_dockerfile(root, out)
            assert out.exists()
            content = out.read_text()
            assert len(content) > 0

    def test_generate_ci_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out = root / ".github" / "workflows" / "ci.yml"
            generate_github_ci(root, out)
            assert out.exists()
