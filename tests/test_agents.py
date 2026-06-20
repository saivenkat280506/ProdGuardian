import pytest
from pathlib import Path
from prodguardian.agents.frontend_agent import FrontendAgent
from prodguardian.agents.backend_agent import BackendAgent
from prodguardian.agents.secrets_agent import SecretsAgent
from prodguardian.agents.manager import AgentManager

FIXTURES = Path(__file__).parent / "fixtures"
MIXED_REPO = FIXTURES / "mixed_repo"


class TestFrontendAgent:
    def test_can_handle_jsx(self):
        agent = FrontendAgent()
        assert agent.can_handle(Path("app.jsx"))
        assert agent.can_handle(Path("app.tsx"))
        assert agent.can_handle(Path("app.js"))
        assert agent.can_handle(Path("app.vue"))

    def test_cannot_handle_python(self):
        agent = FrontendAgent()
        assert not agent.can_handle(Path("app.py"))

    def test_detects_dangerously_set_inner_html(self):
        agent = FrontendAgent()
        content = '<div dangerouslySetInnerHTML={{ __html: data }} />'
        issues = agent.scan(Path("test.jsx"), content)
        assert len(issues) > 0
        assert issues[0]["rule_id"] == "FRONT001"

    def test_detects_eval(self):
        agent = FrontendAgent()
        content = "eval(userInput)"
        issues = agent.scan(Path("test.js"), content)
        assert any("eval()" in i["message"] for i in issues)


class TestBackendAgent:
    def test_can_handle_python(self):
        agent = BackendAgent()
        assert agent.can_handle(Path("app.py"))
        assert agent.can_handle(Path("app.js"))
        assert agent.can_handle(Path("app.ts"))

    def test_cannot_handle_jsx(self):
        agent = BackendAgent()
        assert not agent.can_handle(Path("app.jsx"))
        assert not agent.can_handle(Path("app.vue"))

    def test_scan_python_file(self):
        agent = BackendAgent()
        file_path = FIXTURES / "mixed_repo" / "backend" / "api.py"
        content = file_path.read_text()
        issues = agent.scan(file_path, content)
        assert len(issues) > 0


class TestSecretsAgent:
    def test_can_handle_text_files(self):
        agent = SecretsAgent()
        assert agent.can_handle(Path("secrets.txt"))
        assert agent.can_handle(Path("config.py"))

    def test_cannot_handle_binary(self):
        agent = SecretsAgent()
        assert not agent.can_handle(Path("image.png"))
        assert not agent.can_handle(Path("doc.pdf"))


class TestAgentManager:
    def test_scan_mixed_repo(self):
        # Fixture contains intentional vulns, force include test dirs for the test
        manager = AgentManager(MIXED_REPO, skip_test_dirs=False)
        issues = manager.scan()
        assert len(issues) > 0
        rule_ids = {i["rule_id"] for i in issues}
        assert "FRONT001" in rule_ids or "SEC001" in rule_ids

    def test_scan_returns_list(self):
        manager = AgentManager(MIXED_REPO, skip_test_dirs=False)
        issues = manager.scan()
        assert isinstance(issues, list)
        for issue in issues:
            assert "rule_id" in issue
            assert "severity" in issue
            assert "file" in issue
            assert "line" in issue
            assert "message" in issue
