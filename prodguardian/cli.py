import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from prodguardian.utils.config import get_config_value, load_config
from prodguardian.utils.output import print_issues

console = Console()
logger = logging.getLogger("prodguardian")


@click.group(invoke_without_command=True)
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
@click.option("--config", default=None, type=click.Path(), help="Path to config file")
@click.pass_context
def cli(ctx, verbose, config):
    """ProdGuardian - production readiness CLI"""
    ctx.ensure_object(dict)
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    root = Path.cwd()
    ctx.obj["config"] = load_config(root if config is None else Path(config).parent)
    ctx.obj["root"] = root

    if ctx.invoked_subcommand is None:
        from prodguardian.tui.app import run

        run()
        ctx.exit()


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--parallel/--sequential", default=True, help="Use parallel agents (default) or sequential mode")
@click.option("--workers", default=None, type=int, help="Number of parallel workers (default: auto)")
@click.option("--no-cache", is_flag=True, help="Ignore cached AST results (sequential mode only)")
@click.option("--save-issues", default=None, type=click.Path(), help="Save scan results to JSON file")
@click.pass_context
def scan(ctx, path, parallel, workers, no_cache, save_issues):
    """Scan codebase with AI (Cloud API or Ollama) using your presets and rules.

    Reads source and config files, sends them to your configured LLM, and reports
    leaks that must not ship to production (secrets, env files, debug code, etc.).
    """
    config = ctx.obj["config"]
    root = Path(path).resolve()
    console.print(f"[bold green]ProdGuardian AI scan: {root}[/bold green]")

    try:
        from prodguardian.llm.active_config import (
            bootstrap_llm_from_disk,
            get_scan_llm_settings,
        )
        from prodguardian.llm.codebase_scanner import CodebaseLLMScanner
        from prodguardian.llm.llm_router import prepare_scan_models
        from prodguardian.tui.settings_store import get_presets, get_rules, get_settings, is_llm_configured

        bootstrap_llm_from_disk()

        if not is_llm_configured():
            console.print(
                "[red]Scan requires AI. Configure Cloud API or Ollama in "
                "~/.prodguardian.toml or run prodguardian and click Scan.[/red]"
            )
            sys.exit(1)

        scan_settings = get_scan_llm_settings()
        user_settings = get_settings()
        llm_budget = user_settings.get("llm", {})
        scan_cfg = config.get("scan", {})
        console.print(
            f"[cyan]Scan {scan_settings.describe()} with presets + rules[/cyan]"
        )

        def cli_progress(message: str) -> None:
            console.print(f"[dim]{message}[/dim]")

        ollama_error = prepare_scan_models(scan_settings, on_progress=cli_progress)
        if ollama_error:
            console.print(f"[red]{ollama_error}[/red]")
            sys.exit(1)

        from prodguardian.tui.orchestrator import Orchestrator

        orchestrator = Orchestrator(root)
        orchestrator.set_project(root)

        def on_progress(stage: str, data: dict) -> None:
            msg = data.get("message", stage)
            chunks_total = data.get("chunks_total")
            chunks_done = data.get("chunks_done")
            if chunks_total and chunks_done is not None:
                progress.update(
                    task,
                    description=f"[{stage}] {msg}",
                    completed=chunks_done,
                    total=max(chunks_total, 1),
                )
            else:
                progress.update(task, description=f"[{stage}] {msg}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning...", total=100)
            static_issues = orchestrator._run_static_scan(on_progress=on_progress)
            scanner = CodebaseLLMScanner(
                root,
                get_presets(),
                get_rules(),
                scan_settings=scan_settings,
                max_cost_usd=float(llm_budget.get("max_cost_usd", 0.10)),
                max_tokens=int(llm_budget.get("max_tokens", 32000)),
                skip_test_dirs=scan_cfg.get("skip_test_dirs", True),
                extra_ignore_dirs=scan_cfg.get("ignore_dirs", []),
                groq_chunk_delay=scan_cfg.get("groq_chunk_delay"),
            )
            llm_report = scanner.scan(on_progress=on_progress)
            issues = orchestrator._merge_issues(static_issues, llm_report.issues)
            progress.update(
                task,
                description=(
                    f"Done — {len(issues)} leak(s), {llm_report.api_calls} API call(s)"
                ),
                completed=100,
                total=100,
            )
            if llm_report.chunks_total > 0 and not llm_report.llm_reached_api:
                console.print(
                    f"[red]AI scan made no API calls: {llm_report.stop_reason}[/red]"
                )

        if parallel is False or workers or no_cache:
            console.print(
                "[dim]Note: --parallel/--sequential/--workers/--no-cache are legacy flags. "
                "AI scan always uses your configured LLM.[/dim]"
            )

        print_issues(issues)
        console.print(f"\n[bold]AI scan complete. {len(issues)} leak(s) found.[/bold]")
        console.print("[dim]Add --save-issues results.json to export findings.[/dim]")

        if save_issues:
            save_path = Path(save_issues)
            save_path.write_text(json.dumps(issues, indent=2), encoding="utf-8")
            console.print(f"[cyan]Issues saved to {save_path}[/cyan]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.debug(f"Scan error: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.pass_context
def audit(ctx, path):
    """Check for missing production assets."""
    root = Path(path).resolve()
    try:
        from prodguardian.production.auditor import ProductionAuditor
        auditor = ProductionAuditor(root)
        issues = auditor.audit()
        if not issues:
            console.print("[green]Production readiness looks good![/green]")
        else:
            console.print(f"[yellow]Missing {len(issues)} production assets:[/yellow]")
            print_issues(issues)
            console.print("\n[bold]Run 'prodguardian generate <asset>' to create them.[/bold]")
    except Exception as e:
        console.print(f"[red]Error during audit: {e}[/red]")
        sys.exit(1)


@cli.group()
def generate():
    """Generate missing production assets."""
    pass


@generate.command("dockerfile")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", default="Dockerfile", help="Output file name")
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_dockerfile_cmd(path, output, yes):
    """Generate a Dockerfile."""
    root = Path(path).resolve()
    out_path = root / output
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_dockerfile
        generate_dockerfile(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating Dockerfile: {e}[/red]")
        sys.exit(1)


@generate.command("ci")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_ci_cmd(path, yes):
    """Generate GitHub Actions CI workflow."""
    root = Path(path).resolve()
    out_path = root / ".github" / "workflows" / "ci.yml"
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_github_ci
        generate_github_ci(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating CI: {e}[/red]")
        sys.exit(1)


@generate.command("env")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_env_cmd(path, yes):
    """Generate .env.example from code."""
    root = Path(path).resolve()
    out_path = root / ".env.example"
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_env_example
        generate_env_example(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating .env.example: {e}[/red]")
        sys.exit(1)


@generate.command("compose")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_compose_cmd(path, yes):
    """Generate docker-compose.yml."""
    root = Path(path).resolve()
    out_path = root / "docker-compose.yml"
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_docker_compose
        generate_docker_compose(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating docker-compose.yml: {e}[/red]")
        sys.exit(1)


@generate.command("error-handler")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_error_handler_cmd(path, yes):
    """Generate error handler middleware."""
    root = Path(path).resolve()
    out_path = root / "error_handlers.py"
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_error_handler
        generate_error_handler(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating error handler: {e}[/red]")
        sys.exit(1)


@generate.command("rate-limiter")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--yes", is_flag=True, help="Skip confirmation")
def generate_rate_limiter_cmd(path, yes):
    """Generate rate limiter middleware."""
    root = Path(path).resolve()
    out_path = root / "rate_limiter.py"
    if out_path.exists() and not yes:
        if not click.confirm(f"{out_path} already exists. Overwrite?"):
            return
    try:
        from prodguardian.production.generator import generate_rate_limiter
        generate_rate_limiter(root, out_path)
        console.print(f"[green]Generated {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Error generating rate limiter: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("issue_id")
@click.option("--model", default=None, help="LLM model to use")
@click.pass_context
def explain(ctx, issue_id, model):
    """Explain an issue in natural language (requires API key)."""
    from prodguardian.llm.active_config import bootstrap_llm_from_disk, get_active_llm_config
    from prodguardian.llm.router import LLMRouter
    from prodguardian.tui.settings_store import get_settings

    bootstrap_llm_from_disk()
    config = ctx.obj["config"]
    llm = get_active_llm_config()
    model = model or llm["model"]

    try:
        parts = issue_id.split(":")
        if len(parts) >= 3:
            rule_id = parts[0]
            file_path = ":".join(parts[1:-1])
            line = int(parts[-1])
        else:
            console.print("[red]Issue ID format: RULE001:path/to/file.py:42[/red]")
            return
    except (ValueError, IndexError):
        console.print("[red]Invalid issue ID format. Expected: RULE001:path/to/file.py:42[/red]")
        return

    issue = {
        "rule_id": rule_id,
        "file": file_path,
        "line": line,
        "message": "security issue",
        "severity": "HIGH",
    }

    console.print(f"[cyan]Explaining {issue_id} using {model}...[/cyan]")
    try:
        from prodguardian.llm.fixer import FixGenerator

        llm_budget = get_settings().get("llm", {})
        max_cost = float(llm_budget.get("max_cost_usd", 0.10))
        fixer = FixGenerator(model=model, max_cost_usd=max_cost)
        fixer.router = LLMRouter(
            model=model,
            api_key=llm["api_key"],
            base_url=llm.get("base_url") or None,
        )
        explanation = fixer.explain(issue)
        console.print(f"\n[bold]Explanation:[/bold]\n{explanation}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("issue_id")
@click.option("--model", default=None, help="LLM model to use")
@click.option("--apply", is_flag=True, help="Apply the fix to the file (experimental)")
@click.option("--yes", is_flag=True, help="Skip cost confirmation")
@click.pass_context
def fix(ctx, issue_id, model, apply, yes):
    """Generate a fix for a specific issue (requires API key)."""
    from prodguardian.llm.active_config import bootstrap_llm_from_disk, get_active_llm_config
    from prodguardian.llm.router import LLMRouter
    from prodguardian.tui.settings_store import get_settings

    bootstrap_llm_from_disk()
    config = ctx.obj["config"]
    llm = get_active_llm_config()
    model = model or llm["model"]

    try:
        parts = issue_id.split(":")
        if len(parts) >= 3:
            rule_id = parts[0]
            file_path = ":".join(parts[1:-1])
            line = int(parts[-1])
        else:
            console.print("[red]Issue ID format: RULE001:path/to/file.py:42[/red]")
            return
    except (ValueError, IndexError):
        console.print("[red]Invalid issue ID format. Expected: RULE001:path/to/file.py:42[/red]")
        return

    issue = {
        "rule_id": rule_id,
        "file": file_path,
        "line": line,
        "message": "hardcoded secret" if rule_id == "SEC001" else "security issue",
        "severity": "HIGH",
    }

    if apply:
        console.print("[yellow]⚠ Warning: --apply flag is not yet implemented. "
                      "The fix will be displayed but not applied automatically.[/yellow]")

    console.print(f"[cyan]Generating fix for {issue_id} using {model}...[/cyan]")
    try:
        from prodguardian.llm.budget import estimate_cost
        from prodguardian.llm.fixer import FixGenerator

        llm_budget = get_settings().get("llm", {})
        max_cost = float(llm_budget.get("max_cost_usd", 0.10))

        est_cost = estimate_cost(1000, model)
        if not yes and est_cost > 0.001:
            if not click.confirm(f"This will cost approx ${est_cost:.4f}. Continue?"):
                return

        fixer = FixGenerator(model=model, max_cost_usd=max_cost)
        fixer.router = LLMRouter(
            model=model,
            api_key=llm["api_key"],
            base_url=llm.get("base_url") or None,
        )
        suggestion = fixer.generate_fix(issue)
        console.print(f"\n[bold]Suggested fix:[/bold]\n{suggestion}")
        if apply:
            console.print("[dim]Note: Auto-apply not yet implemented. Copy the fix manually.[/dim]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
