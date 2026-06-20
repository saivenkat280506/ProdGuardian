import re
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from prodguardian.utils.framework_detect import detect_framework

TEMPLATE_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)


def generate_dockerfile(root: Path, output_path: Optional[Path] = None) -> str:
    """Generate a production-grade Dockerfile based on framework."""
    info = detect_framework(root)
    template = env.get_template("Dockerfile.j2")
    content = template.render(
        framework=info["web_framework"] or "generic",
        package_manager=info["package_manager"] or "pip",
        project_type=info["type"],
    )
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content


def generate_github_ci(root: Path, output_path: Optional[Path] = None) -> str:
    template = env.get_template("github-ci.j2")
    info = detect_framework(root)
    content = template.render(
        framework=info["web_framework"] or "generic",
        project_type=info["type"],
        python_version="3.11",
        node_version="20",
    )
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    return content


def _scan_env_vars(root: Path) -> set[str]:
    """Scan code for os.getenv calls and suggest .env.example."""
    vars_found: set[str] = set()
    for file in root.rglob("*.py"):
        try:
            content = file.read_text(encoding="utf-8")
            matches = re.findall(r'os\.getenv\(["\']([A-Z_]+)["\']', content)
            vars_found.update(matches)
            matches = re.findall(r'os\.environ\[["\']([A-Z_]+)["\']', content)
            vars_found.update(matches)
        except Exception:
            pass
    for file in root.rglob("*.js"):
        try:
            content = file.read_text(encoding="utf-8")
            matches = re.findall(r'process\.env\.([A-Z_]+)', content)
            vars_found.update(matches)
        except Exception:
            pass
    return vars_found


def generate_env_example(root: Path, output_path: Optional[Path] = None) -> str:
    vars_found = _scan_env_vars(root)
    template = env.get_template("env-example.j2")
    content = template.render(variables=sorted(vars_found))
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content


def generate_docker_compose(root: Path, output_path: Optional[Path] = None) -> str:
    info = detect_framework(root)
    template = env.get_template("docker-compose.j2")
    content = template.render(
        framework=info["web_framework"] or "generic",
        project_type=info["type"],
    )
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content


def generate_error_handler(root: Path, output_path: Optional[Path] = None) -> str:
    info = detect_framework(root)
    template = env.get_template("error-handler.j2")
    content = template.render(framework=info["web_framework"] or "flask")
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content


def generate_rate_limiter(root: Path, output_path: Optional[Path] = None) -> str:
    info = detect_framework(root)
    template = env.get_template("rate-limiter.j2")
    content = template.render(framework=info["web_framework"] or "flask")
    if output_path:
        output_path.write_text(content, encoding="utf-8")
    return content
