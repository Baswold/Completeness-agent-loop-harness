import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.style import Style
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
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
    "purple": "#a855f7",
}

pt_style = PTStyle.from_dict({
    "prompt": "#4285f4 bold",
    "": "#ffffff",
})


def print_banner():
    console.print()
    banner = Text()
    banner.append("✦ ", style=f"bold {COLORS['primary']}")
    banner.append("Completeness Loop", style="bold white")
    banner.append("  ", style="")
    banner.append("autonomous coding agent", style=COLORS["muted"])
    console.print(Panel(
        banner,
        border_style=COLORS["primary"],
        box=box.ROUNDED,
        padding=(0, 2),
    ))


def print_step(icon: str, msg: str, style: str = "white"):
    console.print(f"  {icon}  {msg}", style=style)


def print_error(msg: str):
    console.print(f"  [{COLORS['error']}]✗[/]  {msg}")


def print_success(msg: str):
    console.print(f"  [{COLORS['success']}]✓[/]  {msg}")


def print_info(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    console.print(f"  [{COLORS['muted']}]{ts}[/]  {msg}")


def progress_bar(score: int, width: int = 30) -> Text:
    filled = int(score / 100 * width)
    text = Text()
    text.append("█" * filled, style=COLORS["success"])
    text.append("░" * (width - filled), style=COLORS["muted"])
    text.append(f" {score}%", style="bold white")
    return text


def format_duration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def detect_idea_file(directory: Path) -> "Path | None":
    candidates = ["idea.md", "IDEA.md", "spec.md", "SPEC.md", "README.md", "project.md"]
    for name in candidates:
        path = directory / name
        if path.exists():
            return path
    for path in directory.glob("*.md"):
        return path
    return None


def setup_workspace(base_dir: Path) -> Path:
    workspace = base_dir / "workspace"
    workspace.mkdir(exist_ok=True)
    return workspace


def init_git(workspace: Path) -> bool:
    git_dir = workspace / ".git"
    if git_dir.exists():
        return False
    
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.email", "agent@completeness-loop"], cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Completeness Loop"], cwd=workspace, capture_output=True)
    
    gitignore = workspace / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\n*.pyc\n.env\nnode_modules/\n.DS_Store\n")
    
    return True


def copy_idea_to_workspace(idea_file: Path, workspace: Path):
    dest = workspace / "idea.md"
    if not dest.exists():
        dest.write_text(idea_file.read_text())
    return dest


def print_cycle_result(result: CycleResult, phase: str):
    console.print()
    
    phase_color = COLORS["cyan"] if phase == "implementation" else COLORS["purple"]
    
    header = Text()
    header.append(f"Cycle {result.cycle_number}", style="bold white")
    header.append(f"  ", style="")
    header.append(f"[{phase}]", style=phase_color)
    
    content = Text()
    content.append("Completeness  ")
    content.append_text(progress_bar(result.completeness_score))
    content.append(f"\nDuration      {result.duration_seconds:.1f}s")
    
    if result.agent1_response:
        tokens = result.agent1_response.usage.total_tokens
        iters = result.agent1_response.iterations
        content.append(f"\nImplementer   {tokens:,} tokens, {iters} tool calls")
    
    if result.agent2_review:
        tokens = result.agent2_review.usage.total_tokens
        content.append(f"\nReviewer      {tokens:,} tokens")
    
    border_color = COLORS["success"] if result.completeness_score >= 90 else COLORS["primary"]
    
    console.print(Panel(
        content,
        title=header,
        border_style=border_color,
        box=box.ROUNDED,
    ))
    
    if result.agent2_review:
        if result.agent2_review.completed_items:
            console.print(f"  [{COLORS['success']}]Done:[/]")
            for item in result.agent2_review.completed_items[:3]:
                console.print(f"    [green]•[/] {item[:70]}")
        
        if result.agent2_review.remaining_work:
            console.print(f"  [{COLORS['warning']}]Next:[/]")
            for item in result.agent2_review.remaining_work[:3]:
                console.print(f"    [yellow]•[/] {item[:70]}")
    
    if result.error:
        print_error(result.error)
    
    console.print()


def print_final_summary(status: dict, elapsed: float):
    console.print()
    
    if status["is_complete"]:
        state_label = "COMPLETE"
        state_color = COLORS["success"]
        icon = "✓"
    elif status.get("is_paused"):
        state_label = "PAUSED"
        state_color = COLORS["warning"]
        icon = "⏸"
    else:
        state_label = "STOPPED"
        state_color = COLORS["muted"]
        icon = "■"
    
    content = Text()
    content.append(f"{icon} ", style=f"bold {state_color}")
    content.append(state_label, style=f"bold {state_color}")
    content.append("\n\n")
    content.append("Score     ")
    content.append_text(progress_bar(status["current_score"]))
    content.append(f"\nPhase     {status.get('phase', 'implementation')}")
    content.append(f"\nCycles    {status['cycle_count']}")
    content.append(f"\nRuntime   {format_duration(elapsed)}")
    content.append(f"\nTokens    {status['total_tokens']:,}")
    
    console.print(Panel(
        content,
        title="Session Summary",
        border_style=state_color,
        box=box.DOUBLE,
    ))
    console.print()


def print_help():
    help_text = """[bold]Interactive Commands:[/]
  [cyan]go[/] / [cyan]start[/]     Start the autonomous loop
  [cyan]resume[/]         Resume a paused session
  [cyan]status[/]         Show current progress
  [cyan]history[/]        Show completeness score history
  [cyan]config[/]         Generate config.yaml
  [cyan]backends[/]       List available LLM backends
  [cyan]help[/]           Show this help
  [cyan]quit[/] / [cyan]q[/]       Exit

[bold]Quick Start:[/]
  Just type [cyan]go[/] and press Enter to start!
  The agent will read your idea.md and build the project.
  Press [bold]Ctrl+C[/] anytime to pause."""
    console.print(Panel(help_text, border_style=COLORS["muted"], box=box.ROUNDED, title="Help"))


class CompletenessREPL:
    def __init__(self, base_dir: "Path | None" = None):
        self.base_dir = base_dir or Path.cwd()
        self.config = LoopConfig()
        self.workspace = None
        self.idea_file = None
        self.orchestrator = None
        self.running = False
        self.history = InMemoryHistory()
    
    def get_prompt_text(self):
        return HTML('<prompt>❯ </prompt>')
    
    def auto_detect(self) -> bool:
        self.idea_file = detect_idea_file(self.base_dir)
        if not self.idea_file:
            return False
        self.workspace = setup_workspace(self.base_dir)
        return True
    
    def print_setup_info(self):
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style=COLORS["muted"], width=12)
        table.add_column(style="white")
        
        idea_display = self.idea_file.name if self.idea_file else "[not found]"
        workspace_display = str(self.workspace.relative_to(self.base_dir)) if self.workspace else "[not set]"
        
        table.add_row("Idea file", idea_display)
        table.add_row("Workspace", workspace_display)
        table.add_row("Backend", self.config.model.backend)
        table.add_row("Model", self.config.model.name)
        
        console.print()
        console.print(table)
        console.print()
    
    def cmd_go(self):
        if not self.idea_file or not self.workspace:
            print_error("No idea.md found in current directory")
            console.print(f"  [{COLORS['muted']}]Create an idea.md file describing your project[/]")
            return
        
        console.print()
        
        workspace = self.workspace
        with console.status("[bold blue]Setting up workspace...", spinner="dots"):
            workspace.mkdir(exist_ok=True)
            idea_in_workspace = copy_idea_to_workspace(self.idea_file, workspace)
            git_initialized = init_git(workspace)
        
        print_success(f"Workspace ready: {self.workspace}")
        if git_initialized:
            print_success("Git repository initialized")
        print_success(f"Project spec: {idea_in_workspace.name}")
        
        console.print()
        
        initial_prompt = f"""Build the complete project described in @idea.md

Read the specification file carefully, then implement everything it describes.
Work systematically through all requirements.
Create proper project structure, write clean code, and ensure it runs correctly.
Commit your progress after completing each major feature.

Start now."""
        
        self._run_loop(self.idea_file, self.workspace, initial_prompt=initial_prompt)
    
    def cmd_resume(self):
        if not self.workspace:
            print_error("No workspace found")
            return
        
        state_file = self.workspace / ".completeness_state.json"
        if not state_file.exists():
            print_error("No saved session to resume")
            console.print(f"  [{COLORS['muted']}]Use 'go' to start a new session[/]")
            return
        
        self._run_loop(self.idea_file, self.workspace, resume=True)
    
    def _run_loop(self, idea_path, workspace_path, resume=False, initial_prompt=None):
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
            f"{action} autonomous development loop\n\n"
            f"The agent will implement your project, commit changes,\n"
            f"and iterate until complete. Press [bold]Ctrl+C[/] to pause.",
            border_style=COLORS["cyan"],
            box=box.ROUNDED,
            title="[bold]Agent Running[/]"
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
    
    def cmd_status(self):
        if not self.workspace:
            print_error("No workspace configured")
            return
        
        state_file = self.workspace / ".completeness_state.json"
        if not state_file.exists():
            print_info("No active session. Type 'go' to start.")
            return
        
        with open(state_file) as f:
            state = json.load(f)
        
        history = state.get("completeness_history", [])
        latest_score = history[-1]["score"] if history else 0
        
        content = Text()
        content.append("Score     ")
        content.append_text(progress_bar(latest_score))
        content.append(f"\nPhase     {state.get('phase', 'implementation')}")
        content.append(f"\nCycles    {state.get('cycle_count', 0)}")
        content.append(f"\nComplete  {'Yes' if state.get('is_complete') else 'No'}")
        content.append(f"\nPaused    {'Yes' if state.get('is_paused') else 'No'}")
        
        console.print()
        console.print(Panel(content, title="Status", border_style=COLORS["primary"], box=box.ROUNDED))
        console.print()
    
    def cmd_history(self):
        if not self.workspace:
            print_error("No workspace configured")
            return
        
        state_file = self.workspace / ".completeness_state.json"
        if not state_file.exists():
            print_info("No session history yet.")
            return
        
        with open(state_file) as f:
            state = json.load(f)
        
        history = state.get("completeness_history", [])
        if not history:
            print_info("No cycles completed yet.")
            return
        
        console.print()
        table = Table(title="Completeness History", box=box.ROUNDED, border_style=COLORS["primary"])
        table.add_column("Cycle", style="bold", justify="right", width=6)
        table.add_column("Score", justify="left", width=40)
        table.add_column("Phase", style=COLORS["muted"], width=8)
        
        for entry in history[-15:]:
            cycle = str(entry.get("cycle", "?"))
            score = entry.get("score", 0)
            phase = entry.get("phase", "impl")[:4]
            bar = progress_bar(score, 25)
            table.add_row(cycle, bar, phase)
        
        console.print(table)
        console.print()
    
    def cmd_backends(self):
        console.print()
        console.print(Panel(
            list_backends(),
            title="Available Backends",
            border_style=COLORS["primary"],
            box=box.ROUNDED,
        ))
        console.print()
    
    def cmd_config(self):
        output = Path("config.yaml")
        self.config.save(output)
        print_success(f"Config saved to {output}")
    
    def run(self):
        print_banner()
        
        if self.auto_detect():
            self.print_setup_info()
            console.print(f"  [{COLORS['cyan']}]Type 'go' to start building, or 'help' for options[/]")
        else:
            console.print()
            print_error("No idea.md file found in current directory")
            console.print()
            console.print(f"  [{COLORS['muted']}]Create a file called [bold]idea.md[/] describing your project,[/]")
            console.print(f"  [{COLORS['muted']}]then run this again.[/]")
            console.print()
            console.print(f"  [{COLORS['muted']}]Example idea.md:[/]")
            console.print(f"  [{COLORS['muted']}]  # My Todo App[/]")
            console.print(f"  [{COLORS['muted']}]  Build a command-line todo list manager with...[/]")
            console.print()
            return
        
        console.print()
        
        while True:
            try:
                line = prompt(
                    self.get_prompt_text(),
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
            
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd in ("go", "start", "run"):
                self.cmd_go()
            elif cmd == "resume":
                self.cmd_resume()
            elif cmd == "status":
                self.cmd_status()
            elif cmd in ("history", "score", "scores"):
                self.cmd_history()
            elif cmd == "backends":
                self.cmd_backends()
            elif cmd == "config":
                self.cmd_config()
            elif cmd == "help":
                print_help()
            else:
                print_error(f"Unknown command: {cmd}")
                console.print(f"  [{COLORS['muted']}]Type 'help' for available commands[/]")
        
        console.print()
        console.print(f"[{COLORS['muted']}]Goodbye![/]")
        console.print()


def main():
    base_dir = Path.cwd()
    if len(sys.argv) > 1:
        base_dir = Path(sys.argv[1]).resolve()
    
    repl = CompletenessREPL(base_dir)
    repl.run()


if __name__ == "__main__":
    main()
