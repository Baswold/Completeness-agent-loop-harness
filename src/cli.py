import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import signal
import threading

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.style import Style
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML

from .config import LoopConfig
from .orchestrator import Orchestrator, CycleResult
from .llm import list_backends

console = Console()

COLORS = {
    "primary": "#4285f4",
    "success": "#34a853",
    "warning": "#fbbc04",
    "error": "#ea4335",
    "muted": "#9aa0a6",
    "cyan": "#00bcd4",
}

pt_style = PTStyle.from_dict({
    "prompt": "#4285f4 bold",
    "": "#ffffff",
})


def print_welcome():
    console.print()
    welcome = Text()
    welcome.append("✦ ", style=f"bold {COLORS['primary']}")
    welcome.append("Completeness Loop", style="bold white")
    console.print(Panel(
        welcome,
        border_style=COLORS["primary"],
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    console.print()


def print_config_info(config: LoopConfig):
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style=COLORS["muted"])
    table.add_column(style="white")
    table.add_row("Backend", config.model.backend)
    table.add_row("Model", config.model.name)
    table.add_row("Max cycles", str(config.limits.max_iterations))
    console.print(table)
    console.print()


def print_help():
    console.print()
    help_text = """[bold]Commands:[/]
  [cyan]start[/] <idea.md> <workspace>  Start autonomous loop
  [cyan]resume[/] <workspace>           Resume paused loop
  [cyan]status[/] [workspace]           Show current status
  [cyan]score[/] [workspace]            Show completeness history
  [cyan]backends[/]                     List LLM backends
  [cyan]config[/] [path]                Generate config file
  [cyan]help[/]                         Show this help
  [cyan]quit[/]                         Exit"""
    console.print(Panel(help_text, border_style=COLORS["muted"], box=box.ROUNDED))
    console.print()


def print_error(msg: str):
    console.print(f"[{COLORS['error']}]✗[/] {msg}")


def print_success(msg: str):
    console.print(f"[{COLORS['success']}]✓[/] {msg}")


def print_info(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"[{COLORS['muted']}]{ts}[/] {msg}")


def progress_bar(score: int, width: int = 30) -> Text:
    filled = int(score / 100 * width)
    text = Text()
    text.append("█" * filled, style=COLORS["success"])
    text.append("░" * (width - filled), style=COLORS["muted"])
    text.append(f" {score}%", style="bold white")
    return text


def format_duration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def print_cycle_result(result: CycleResult, phase: str):
    console.print()
    
    header = Text()
    header.append(f"Cycle {result.cycle_number}", style="bold white")
    header.append(f"  [{phase}]", style=COLORS["cyan"])
    
    content = Text()
    content.append("Score: ")
    content.append_text(progress_bar(result.completeness_score))
    content.append(f"\nTime:  {result.duration_seconds:.1f}s")
    
    if result.agent1_response:
        tokens = result.agent1_response.usage.total_tokens
        iters = result.agent1_response.iterations
        content.append(f"\nAgent 1: {tokens:,} tokens, {iters} iterations")
    
    if result.agent2_review:
        tokens = result.agent2_review.usage.total_tokens
        content.append(f"\nAgent 2: {tokens:,} tokens")
    
    console.print(Panel(
        content,
        title=header,
        border_style=COLORS["primary"],
        box=box.ROUNDED,
    ))
    
    if result.agent2_review:
        if result.agent2_review.completed_items:
            console.print(f"  [{COLORS['success']}]Completed:[/]")
            for item in result.agent2_review.completed_items[:3]:
                console.print(f"    + {item[:65]}")
        
        if result.agent2_review.remaining_work:
            console.print(f"  [{COLORS['warning']}]Remaining:[/]")
            for item in result.agent2_review.remaining_work[:3]:
                console.print(f"    - {item[:65]}")
    
    if result.error:
        print_error(result.error)
    
    console.print()


def print_final_summary(status: dict, elapsed: float):
    console.print()
    
    state_label = "COMPLETE" if status["is_complete"] else "PAUSED" if status.get("is_paused") else "STOPPED"
    state_color = COLORS["success"] if status["is_complete"] else COLORS["warning"]
    
    content = Text()
    content.append("Final Score: ")
    content.append_text(progress_bar(status["current_score"]))
    content.append(f"\nPhase:       {status.get('phase', 'implementation')}")
    content.append(f"\nCycles:      {status['cycle_count']}")
    content.append(f"\nRuntime:     {format_duration(elapsed)}")
    content.append(f"\nTokens:      {status['total_tokens']:,}")
    content.append(f"\nStatus:      ")
    content.append(state_label, style=f"bold {state_color}")
    
    console.print(Panel(
        content,
        title="Session Complete",
        border_style=state_color,
        box=box.DOUBLE,
    ))
    console.print()


class CompletenessREPL:
    def __init__(self):
        self.config = LoopConfig()
        self.current_workspace = None
        self.orchestrator = None
        self.running = False
        self.history = InMemoryHistory()
    
    def get_prompt(self):
        return HTML('<prompt>❯ </prompt>')
    
    def cmd_start(self, args):
        if len(args) < 2:
            print_error("Usage: start <idea.md> <workspace>")
            return
        
        idea_path = Path(args[0]).resolve()
        workspace_path = Path(args[1]).resolve()
        
        if not idea_path.exists():
            print_error(f"File not found: {idea_path}")
            return
        
        workspace_path.mkdir(parents=True, exist_ok=True)
        self.current_workspace = workspace_path
        
        console.print()
        console.print(f"[{COLORS['muted']}]Idea:[/]      {idea_path}")
        console.print(f"[{COLORS['muted']}]Workspace:[/] {workspace_path}")
        console.print()
        
        self._run_loop(idea_path, workspace_path, resume=False)
    
    def cmd_resume(self, args):
        if args:
            workspace_path = Path(args[0]).resolve()
        elif self.current_workspace:
            workspace_path = self.current_workspace
        else:
            print_error("Usage: resume <workspace>")
            return
        
        state_file = workspace_path / ".completeness_state.json"
        if not state_file.exists():
            print_error(f"No saved state in {workspace_path}")
            return
        
        idea_file = None
        for f in workspace_path.parent.glob("*.md"):
            idea_file = f
            break
        
        if not idea_file:
            print_error("Cannot find idea file. Use 'start' instead.")
            return
        
        self._run_loop(idea_file, workspace_path, resume=True)
    
    def _run_loop(self, idea_path, workspace_path, resume=False):
        start_time = time.time()
        
        def on_cycle(result):
            phase = self.orchestrator.state.phase if self.orchestrator else "implementation"
            print_cycle_result(result, phase)
        
        def on_status(status):
            print_info(status)
        
        self.orchestrator = Orchestrator(
            workspace=workspace_path,
            idea_file=idea_path,
            config=self.config,
            on_cycle_complete=on_cycle,
            on_status_change=on_status
        )
        
        self.running = True
        action = "Resuming" if resume else "Starting"
        
        console.print(Panel(
            f"{action} autonomous loop... Press [bold]Ctrl+C[/] to pause",
            border_style=COLORS["cyan"],
            box=box.ROUNDED,
        ))
        console.print()
        
        try:
            self.orchestrator.run(resume=resume)
        except KeyboardInterrupt:
            console.print()
            print_info("Pausing loop...")
            self.orchestrator.pause()
        except Exception as e:
            print_error(str(e))
        
        self.running = False
        status = self.orchestrator.get_status()
        print_final_summary(status, time.time() - start_time)
    
    def cmd_status(self, args):
        workspace = Path(args[0]).resolve() if args else self.current_workspace
        if not workspace:
            print_error("Usage: status <workspace>")
            return
        
        state_file = workspace / ".completeness_state.json"
        if not state_file.exists():
            print_error("No session found.")
            return
        
        with open(state_file) as f:
            state = json.load(f)
        
        history = state.get("completeness_history", [])
        latest_score = history[-1]["score"] if history else 0
        
        content = Text()
        content.append(f"Workspace: {workspace}\n", style=COLORS["muted"])
        content.append("Score:     ")
        content.append_text(progress_bar(latest_score))
        content.append(f"\nPhase:     {state.get('phase', 'implementation')}")
        content.append(f"\nCycles:    {state.get('cycle_count', 0)}")
        content.append(f"\nComplete:  {'Yes' if state.get('is_complete') else 'No'}")
        content.append(f"\nPaused:    {'Yes' if state.get('is_paused') else 'No'}")
        
        console.print()
        console.print(Panel(content, title="Status", border_style=COLORS["primary"], box=box.ROUNDED))
        console.print()
    
    def cmd_score(self, args):
        workspace = Path(args[0]).resolve() if args else self.current_workspace
        if not workspace:
            print_error("Usage: score <workspace>")
            return
        
        state_file = workspace / ".completeness_state.json"
        if not state_file.exists():
            print_error("No session found.")
            return
        
        with open(state_file) as f:
            state = json.load(f)
        
        history = state.get("completeness_history", [])
        if not history:
            print_error("No history yet.")
            return
        
        console.print()
        table = Table(title="Completeness History", box=box.ROUNDED, border_style=COLORS["primary"])
        table.add_column("Cycle", style="bold", justify="right")
        table.add_column("Score", justify="left")
        table.add_column("Phase", style=COLORS["muted"])
        
        for entry in history[-15:]:
            cycle = str(entry.get("cycle", "?"))
            score = entry.get("score", 0)
            phase = entry.get("phase", "impl")[:4]
            bar = progress_bar(score, 20)
            table.add_row(cycle, bar, phase)
        
        console.print(table)
        console.print()
    
    def cmd_backends(self, args):
        console.print()
        console.print(Panel(
            list_backends(),
            title="Available Backends",
            border_style=COLORS["primary"],
            box=box.ROUNDED,
        ))
        console.print()
    
    def cmd_config(self, args):
        output = Path(args[0]) if args else Path("config.yaml")
        self.config.save(output)
        print_success(f"Config saved to {output}")
    
    def run(self):
        print_welcome()
        print_config_info(self.config)
        print_help()
        
        while True:
            try:
                line = prompt(
                    self.get_prompt(),
                    history=self.history,
                    style=pt_style,
                ).strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                if self.running:
                    continue
                console.print()
                break
            
            if not line:
                continue
            
            parts = line.split()
            cmd = parts[0].lower()
            args = parts[1:]
            
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "start":
                self.cmd_start(args)
            elif cmd == "resume":
                self.cmd_resume(args)
            elif cmd == "status":
                self.cmd_status(args)
            elif cmd == "score":
                self.cmd_score(args)
            elif cmd == "backends":
                self.cmd_backends(args)
            elif cmd == "config":
                self.cmd_config(args)
            elif cmd == "help":
                print_help()
            else:
                print_error(f"Unknown command: {cmd}")
                console.print(f"[{COLORS['muted']}]Type 'help' for available commands[/]")
        
        console.print()
        console.print(f"[{COLORS['muted']}]Goodbye![/]")
        console.print()


def main():
    repl = CompletenessREPL()
    repl.run()


if __name__ == "__main__":
    main()
