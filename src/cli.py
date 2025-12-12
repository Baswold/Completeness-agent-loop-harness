import click
import time
from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.style import Style
from datetime import datetime, timedelta
import threading
import signal
import sys

from .config import LoopConfig
from .orchestrator import Orchestrator, CycleResult

console = Console()


class Dashboard:
    def __init__(self):
        self.status = "Initializing..."
        self.cycle = 0
        self.score = 0
        self.phase = "setup"
        self.agent1_tokens = 0
        self.agent2_tokens = 0
        self.elapsed: float = 0.0
        self.history = []
        self.recent_logs = []
        self.is_running = True
    
    def update_cycle(self, result: CycleResult):
        self.cycle = result.cycle_number
        self.score = result.completeness_score
        
        if result.agent1_response:
            self.agent1_tokens += result.agent1_response.usage.total_tokens
        if result.agent2_review:
            self.agent2_tokens += result.agent2_review.usage.total_tokens
        
        self.history.append({
            "cycle": result.cycle_number,
            "score": result.completeness_score,
            "time": datetime.now()
        })
        
        if result.is_complete:
            self.phase = "complete"
        elif result.completeness_score >= 70:
            self.phase = "testing"
        else:
            self.phase = "implementation"
        
        log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] Cycle {result.cycle_number}: {result.completeness_score}%"
        if result.error:
            log_entry += f" (Error: {result.error[:50]})"
        self.recent_logs.append(log_entry)
        self.recent_logs = self.recent_logs[-10:]
    
    def update_status(self, status: str):
        self.status = status
    
    def render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=5)
        )
        
        layout["main"].split_row(
            Layout(name="stats", ratio=1),
            Layout(name="logs", ratio=2)
        )
        
        phase_colors = {
            "setup": "yellow",
            "implementation": "blue",
            "testing": "cyan",
            "complete": "green"
        }
        phase_color = phase_colors.get(self.phase, "white")
        
        header = Table.grid(expand=True)
        header.add_column(justify="left", ratio=1)
        header.add_column(justify="center", ratio=2)
        header.add_column(justify="right", ratio=1)
        
        elapsed_str = str(timedelta(seconds=int(self.elapsed)))
        header.add_row(
            Text("Completeness Loop", style="bold magenta"),
            Text(f"[{self.phase.upper()}]", style=f"bold {phase_color}"),
            Text(f"Elapsed: {elapsed_str}", style="dim")
        )
        layout["header"].update(Panel(header, style="bold"))
        
        stats_table = Table(show_header=False, box=None, padding=(0, 1))
        stats_table.add_column("Label", style="dim")
        stats_table.add_column("Value", style="bold")
        
        score_style = "green" if self.score >= 95 else "yellow" if self.score >= 50 else "red"
        stats_table.add_row("Cycle", str(self.cycle))
        stats_table.add_row("Score", Text(f"{self.score}%", style=score_style))
        stats_table.add_row("Agent 1 Tokens", f"{self.agent1_tokens:,}")
        stats_table.add_row("Agent 2 Tokens", f"{self.agent2_tokens:,}")
        stats_table.add_row("Total Tokens", f"{self.agent1_tokens + self.agent2_tokens:,}")
        
        if self.history:
            progress_bar = self._make_progress_bar()
            stats_table.add_row("Progress", progress_bar)
        
        layout["stats"].update(Panel(stats_table, title="Statistics", border_style="blue"))
        
        logs_text = Text()
        for log in self.recent_logs:
            logs_text.append(log + "\n")
        layout["logs"].update(Panel(logs_text, title="Activity Log", border_style="green"))
        
        footer_text = Text(self.status, style="italic")
        layout["footer"].update(Panel(footer_text, title="Status", border_style="dim"))
        
        return layout
    
    def _make_progress_bar(self) -> Text:
        bar_width = 20
        filled = int(self.score / 100 * bar_width)
        empty = bar_width - filled
        
        bar = Text()
        bar.append("█" * filled, style="green")
        bar.append("░" * empty, style="dim")
        bar.append(f" {self.score}%")
        return bar


@click.group()
def cli():
    """Completeness Loop - Autonomous Multi-Agent Coding System"""
    pass


@cli.command()
@click.option("--idea", "-i", required=True, type=click.Path(exists=True), help="Path to idea.md specification file")
@click.option("--workspace", "-w", required=True, type=click.Path(), help="Path to workspace directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config.yaml file")
@click.option("--resume", "-r", is_flag=True, help="Resume from saved state")
def start(idea: str, workspace: str, config: str, resume: bool):
    """Start or resume a completeness loop task"""
    idea_path = Path(idea).resolve()
    workspace_path = Path(workspace).resolve()
    
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    if config:
        loop_config = LoopConfig.load(Path(config))
    else:
        loop_config = LoopConfig()
    
    dashboard = Dashboard()
    
    def on_cycle_complete(result: CycleResult):
        dashboard.update_cycle(result)
    
    def on_status_change(status: str):
        dashboard.update_status(status)
    
    orchestrator = Orchestrator(
        workspace=workspace_path,
        idea_file=idea_path,
        config=loop_config,
        on_cycle_complete=on_cycle_complete,
        on_status_change=on_status_change
    )
    
    stop_event = threading.Event()
    
    def signal_handler(sig, frame):
        console.print("\n[yellow]Pausing loop... Please wait.[/yellow]")
        orchestrator.pause()
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    def run_loop():
        try:
            orchestrator.run(resume=resume)
        except Exception as e:
            dashboard.update_status(f"Error: {str(e)}")
        finally:
            dashboard.is_running = False
    
    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    
    start_time = time.time()
    
    try:
        with Live(dashboard.render(), console=console, refresh_per_second=2) as live:
            while dashboard.is_running and not stop_event.is_set():
                dashboard.elapsed = time.time() - start_time
                live.update(dashboard.render())
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    
    loop_thread.join(timeout=5)
    
    status = orchestrator.get_status()
    console.print("\n")
    console.print(Panel(
        f"[bold]Final Status[/bold]\n\n"
        f"Cycles: {status['cycle_count']}\n"
        f"Score: {status['current_score']}%\n"
        f"Total Tokens: {status['total_tokens']:,}\n"
        f"Complete: {'Yes' if status['is_complete'] else 'No'}",
        title="Session Complete",
        border_style="green" if status['is_complete'] else "yellow"
    ))


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
def status(workspace: str):
    """Check status of a running or completed loop"""
    workspace_path = Path(workspace).resolve()
    state_file = workspace_path / ".completeness_state.json"
    
    if not state_file.exists():
        console.print("[red]No state file found. Loop may not have been started.[/red]")
        return
    
    import json
    with open(state_file) as f:
        state = json.load(f)
    
    table = Table(title="Loop Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Cycles", str(state.get("cycle_count", 0)))
    table.add_row("Complete", "Yes" if state.get("is_complete") else "No")
    table.add_row("Paused", "Yes" if state.get("is_paused") else "No")
    
    history = state.get("completeness_history", [])
    if history:
        latest = history[-1]
        table.add_row("Latest Score", f"{latest.get('score', 0)}%")
    
    a1_usage = state.get("total_agent1_usage", {})
    a2_usage = state.get("total_agent2_usage", {})
    table.add_row("Agent 1 Tokens", f"{a1_usage.get('total_tokens', 0):,}")
    table.add_row("Agent 2 Tokens", f"{a2_usage.get('total_tokens', 0):,}")
    
    console.print(table)


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
@click.option("--tail", "-n", default=20, help="Number of log entries to show")
def logs(workspace: str, tail: int):
    """View recent activity logs"""
    workspace_path = Path(workspace).resolve()
    log_file = workspace_path / "completeness_loop.log"
    
    if not log_file.exists():
        console.print("[yellow]No log file found.[/yellow]")
        return
    
    with open(log_file) as f:
        lines = f.readlines()
    
    for line in lines[-tail:]:
        console.print(line.rstrip())


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
def score(workspace: str):
    """Check current completeness score and history"""
    workspace_path = Path(workspace).resolve()
    state_file = workspace_path / ".completeness_state.json"
    
    if not state_file.exists():
        console.print("[red]No state file found.[/red]")
        return
    
    import json
    with open(state_file) as f:
        state = json.load(f)
    
    history = state.get("completeness_history", [])
    
    if not history:
        console.print("[yellow]No completeness history yet.[/yellow]")
        return
    
    table = Table(title="Completeness History")
    table.add_column("Cycle", style="cyan")
    table.add_column("Score", style="green")
    table.add_column("Timestamp", style="dim")
    
    for entry in history[-20:]:
        score_val = entry.get("score", 0)
        style = "green" if score_val >= 95 else "yellow" if score_val >= 50 else "red"
        table.add_row(
            str(entry.get("cycle", "?")),
            Text(f"{score_val}%", style=style),
            entry.get("timestamp", "")[:19]
        )
    
    console.print(table)
    
    if history:
        latest = history[-1].get("score", 0)
        bar_width = 40
        filled = int(latest / 100 * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        console.print(f"\n[bold]Current Score:[/bold] [{bar}] {latest}%")


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output path for config file")
def init_config(output: str):
    """Generate a default configuration file"""
    config = LoopConfig()
    output_path = Path(output) if output else Path("config.yaml")
    config.save(output_path)
    console.print(f"[green]Configuration saved to {output_path}[/green]")


def main():
    cli()


if __name__ == "__main__":
    main()
