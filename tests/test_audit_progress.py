from pathlib import Path

from prodguardian.production.auditor import ProductionAuditor


def test_auditor_emits_progress_stages(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "README.md").write_text("# App\n")
    (project / ".gitignore").write_text("*\n")

    stages: list[str] = []

    def on_progress(stage: str, data: dict) -> None:
        stages.append(stage)

    auditor = ProductionAuditor(project)
    auditor.audit(on_progress=on_progress)

    assert stages[0] == "init"
    assert "core" in stages
    assert "runtime" in stages
    assert "security" in stages
    assert "ops" in stages
    assert "report" in stages
    assert stages[-1] == "done"


def test_auditor_emits_sub_progress_within_runtime(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    (project / "README.md").write_text("# App\n")

    runtime_messages: list[str] = []

    def on_progress(stage: str, data: dict) -> None:
        if stage == "runtime":
            runtime_messages.append(data.get("message", ""))

    auditor = ProductionAuditor(project)
    auditor.audit(on_progress=on_progress)

    assert len(runtime_messages) >= 3
    assert any("Checking" in msg for msg in runtime_messages)


def test_auditor_progress_without_callback(tmp_path):
    project = tmp_path / "app"
    project.mkdir()
    auditor = ProductionAuditor(project)
    issues = auditor.audit()
    assert isinstance(issues, list)