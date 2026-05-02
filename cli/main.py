from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from typing import Dict

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

from core.config import load_suite
from core.models import RunSummary
from core.runner import TestRunner
from core.storage import ResultStorage
from evaluators.aggregator import compute_regression_delta

console = Console()

CATEGORIES = [
    "instruction_loss",
    "retrieval_overshadowing",
    "position_bias",
    "answer_truncation",
    "multi_turn_memory_decay",
    "contradiction_long_context",
    "citation_drift",
    "hallucination_overload",
]

CAT_SHORT = {
    "instruction_loss": "INST",
    "retrieval_overshadowing": "RETR",
    "position_bias": "POSN",
    "answer_truncation": "TRUNC",
    "multi_turn_memory_decay": "MEM",
    "contradiction_long_context": "CONTR",
    "citation_drift": "CITE",
    "hallucination_overload": "HALL",
}

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def _is_run_id(s: str) -> bool:
    return bool(_UUID_RE.match(s))


@click.group()
@click.version_option(version="0.1.0", prog_name="contextcrash")
def cli():
    """ContextCrash - LLM reliability benchmarking for RAG pipelines."""
    pass


@cli.command()
@click.argument("suite_file", type=click.Path(exists=True))
@click.option("--db", default=None, help="Override DuckDB path from suite config")
@click.option("--models", default=None, help="Comma-separated model overrides")
@click.option("--output", type=click.Choice(["rich", "json"]), default="rich")
def run(suite_file: str, db: str | None, models: str | None, output: str):
    """Run a benchmark suite against configured models.

    \b
    Example:
        contextcrash run examples/suite.yaml
        contextcrash run examples/suite.yaml --models gpt-4o,claude-opus-4-5
    """
    config = load_suite(suite_file)

    if db:
        config.db_path = db
    if models:
        config.models = [m.strip() for m in models.split(",")]

    storage = ResultStorage(config.db_path)

    if output == "rich":
        console.print(
            Panel.fit(
                f"[bold cyan]ContextCrash[/bold cyan]  suite=[yellow]{config.suite_name}[/yellow]  "
                f"models=[green]{', '.join(config.models)}[/green]  "
                f"tests=[white]{len(config.test_cases)}[/white]",
                border_style="cyan",
            )
        )

    runner = TestRunner(config, storage)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        total_tasks = len(config.models) * len(config.test_cases)
        task = progress.add_task("Running tests...", total=total_tasks)

        original_run_single = runner._run_single

        async def tracked_run_single(run_id, model, tc):
            result = await original_run_single(run_id, model, tc)
            progress.advance(task)
            return result

        runner._run_single = tracked_run_single
        summaries = asyncio.run(runner.run_suite())

    if output == "json":
        print(json.dumps({m: s.model_dump(mode="json") for m, s in summaries.items()}, indent=2, default=str))
    else:
        _print_summaries(summaries)
        _print_heatmap(summaries)
        # ITEM 3 — show per-model, per-category cost breakdown
        if summaries:
            run_id = next(iter(summaries.values())).run_id
            _print_cost_breakdown(storage, run_id)


@cli.command()
@click.argument("baseline")
@click.argument("candidate")
@click.option("--db", default="./data/results.duckdb", help="DuckDB path (required when using run IDs)")
@click.option("--output", type=click.Choice(["rich", "json"]), default="rich")
def compare(baseline: str, candidate: str, db: str, output: str):
    """Compare two suites by YAML file or stored run ID.

    \b
    Pass YAML file paths to run fresh benchmarks, or run UUIDs to compare
    stored results without re-running.  Both arguments must be the same type.

    \b
    Examples:
        contextcrash compare examples/baseline.yaml examples/candidate.yaml
        contextcrash compare <run-uuid-1> <run-uuid-2> --db ./data/results.duckdb
    """
    baseline_is_id = _is_run_id(baseline)
    candidate_is_id = _is_run_id(candidate)

    if baseline_is_id != candidate_is_id:
        console.print("[red]Both arguments must be the same type: both run IDs or both file paths.[/red]")
        sys.exit(1)

    storage = ResultStorage(db)

    if baseline_is_id:
        # ITEM 5 — load existing results from DB, no re-run needed
        baseline_list = storage.get_summaries_for_run(baseline)
        candidate_list = storage.get_summaries_for_run(candidate)

        if not baseline_list:
            console.print(f"[red]No data found for baseline run: {baseline}[/red]")
            sys.exit(1)
        if not candidate_list:
            console.print(f"[red]No data found for candidate run: {candidate}[/red]")
            sys.exit(1)

        baseline_summaries = {s.model: s for s in baseline_list}
        candidate_summaries = {s.model: s for s in candidate_list}
        baseline_name = f"run:{baseline[:8]}…"
        candidate_name = f"run:{candidate[:8]}…"
    else:
        if not os.path.exists(baseline):
            console.print(f"[red]File not found: {baseline}[/red]")
            sys.exit(1)
        if not os.path.exists(candidate):
            console.print(f"[red]File not found: {candidate}[/red]")
            sys.exit(1)

        baseline_config = load_suite(baseline)
        candidate_config = load_suite(candidate)
        baseline_config.db_path = db
        candidate_config.db_path = db

        console.print(Panel.fit(
            f"[bold cyan]ContextCrash Compare[/bold cyan]\n"
            f"  baseline: [yellow]{baseline_config.suite_name}[/yellow]\n"
            f"  candidate: [yellow]{candidate_config.suite_name}[/yellow]",
            border_style="cyan",
        ))

        baseline_summaries = asyncio.run(TestRunner(baseline_config, storage).run_suite())
        candidate_summaries = asyncio.run(TestRunner(candidate_config, storage).run_suite())
        baseline_name = baseline_config.suite_name
        candidate_name = candidate_config.suite_name

    common_models = set(baseline_summaries) & set(candidate_summaries)
    if not common_models:
        console.print("[red]No common models between baseline and candidate.[/red]")
        sys.exit(1)

    comparison_data = {}
    for model in sorted(common_models):
        deltas = compute_regression_delta(baseline_summaries[model], candidate_summaries[model])
        comparison_data[model] = {
            "baseline_failure_rate": baseline_summaries[model].failure_rate,
            "candidate_failure_rate": candidate_summaries[model].failure_rate,
            "overall_delta": candidate_summaries[model].failure_rate - baseline_summaries[model].failure_rate,
            "category_deltas": deltas,
        }

    if output == "json":
        print(json.dumps(comparison_data, indent=2))
    else:
        _print_comparison(comparison_data, baseline_name, candidate_name)


# ── output helpers ────────────────────────────────────────────────────────────

def _print_summaries(summaries: Dict[str, RunSummary]) -> None:
    table = Table(title="Run Results", box=box.ROUNDED, show_lines=True)
    table.add_column("Model", style="cyan")
    table.add_column("Tests", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Failure Rate", justify="right")
    table.add_column("Avg Latency (ms)", justify="right")
    table.add_column("Disputed", justify="right")
    table.add_column("Total Cost", justify="right")

    for model, summary in summaries.items():
        fr = summary.failure_rate
        color = "red" if fr > 0.5 else "yellow" if fr > 0.2 else "green"
        table.add_row(
            model,
            str(summary.total_tests),
            str(summary.failed_tests),
            f"[{color}]{fr:.1%}[/{color}]",
            f"{summary.avg_latency_ms:.0f}",
            str(summary.disputed_count),
            f"${summary.total_cost_usd:.4f}",
        )

    console.print(table)


def _print_heatmap(summaries: Dict[str, RunSummary]) -> None:
    table = Table(
        title="Failure Heatmap (% failed by category)",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Model", style="cyan", no_wrap=True)

    for cat in CATEGORIES:
        table.add_column(CAT_SHORT[cat], justify="center", width=7)

    for model, summary in summaries.items():
        cells = []
        for cat in CATEGORIES:
            rate = summary.failure_by_category.get(cat, None)
            if rate is None:
                cells.append("[dim]  --  [/dim]")
            else:
                color = "red" if rate > 0.5 else "yellow" if rate > 0.2 else "green"
                cells.append(f"[{color}]{rate:.0%}[/{color}]")
        table.add_row(model, *cells)

    console.print(table)
    console.print(
        "  [green]■ <20%[/green]  [yellow]■ 20-50%[/yellow]  [red]■ >50%[/red]   "
        + "  ".join(f"{v}={k}" for k, v in CAT_SHORT.items())
    )


def _print_cost_breakdown(storage: ResultStorage, run_id: str) -> None:
    """ITEM 3 — per-model, per-category cost and performance breakdown."""
    rows = storage.get_model_cost_summaries(run_id)
    if not rows:
        return

    table = Table(
        title="Cost & Performance by Model + Category",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Model", style="cyan")
    table.add_column("Category", style="dim")
    table.add_column("Tests", justify="right")
    table.add_column("Failure Rate", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Est. Cost (USD)", justify="right")

    for row in rows:
        fr = row["failure_rate"]
        color = "red" if fr > 0.5 else "yellow" if fr > 0.2 else "green"
        table.add_row(
            row["model"],
            row["failure_category"],
            str(row["test_count"]),
            f"[{color}]{fr:.1%}[/{color}]",
            f"{row['avg_score']:.2f}",
            f"${row['estimated_cost_usd']:.5f}",
        )

    console.print(table)


def _print_comparison(data: dict, baseline_name: str, candidate_name: str) -> None:
    for model, d in data.items():
        overall_delta = d["overall_delta"]
        delta_color = "red" if overall_delta > 0 else "green" if overall_delta < 0 else "white"

        console.print(f"\n[bold cyan]{model}[/bold cyan]")
        console.print(
            f"  Overall: {baseline_name} [yellow]{d['baseline_failure_rate']:.1%}[/yellow] → "
            f"{candidate_name} [yellow]{d['candidate_failure_rate']:.1%}[/yellow]  "
            f"delta=[{delta_color}]{overall_delta:+.1%}[/{delta_color}]"
        )

        table = Table(box=box.SIMPLE, padding=(0, 2))
        table.add_column("Category", style="dim")
        table.add_column("Delta", justify="right")
        table.add_column("Signal")
        table.add_column("Status")

        # Sort by magnitude, show all categories with non-trivial change
        for cat, delta in sorted(d["category_deltas"].items(), key=lambda x: -abs(x[1])):
            if abs(delta) < 0.01:
                continue
            color = "red" if delta > 0 else "green"
            signal = "▲ regression" if delta > 0 else "▼ improvement"
            status = "[bold red]REGRESSION[/bold red]" if delta > 0 else "[bold green]OK[/bold green]"
            table.add_row(
                cat,
                f"[{color}]{delta:+.1%}[/{color}]",
                f"[{color}]{signal}[/{color}]",
                status,
            )

        console.print(table)


def main():
    cli()


if __name__ == "__main__":
    main()
