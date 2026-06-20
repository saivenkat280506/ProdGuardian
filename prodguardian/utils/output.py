from rich.console import Console
from rich.table import Table

console = Console()


def print_issues(issues):
    if not issues:
        console.print("[green]No issues found![/green]")
        return

    table = Table(title="Security Issues Found")
    table.add_column("Rule", style="cyan")
    table.add_column("Severity", style="red")
    table.add_column("File", style="yellow")
    table.add_column("Line", style="blue")
    table.add_column("Message")

    for issue in issues:
        table.add_row(
            issue.get("rule_id", "unknown"),
            issue.get("severity", "MEDIUM"),
            issue.get("file", ""),
            str(issue.get("line", 0)),
            issue.get("message", ""),
        )
    console.print(table)
