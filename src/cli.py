import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
from typing import Optional

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


def detect_idea_file(directory: Path) -> Optional[Path]:
    candidates = ["idea.md", "IDEA.md", "spec.md", "SPEC.md", "project.md"]
    for name in candidates:
        path = directory / name
        if path.exists():
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


def print_cycle_result(result: CycleResult, phase: str, state=None):
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

    # Show cycle-specific metrics if available, otherwise show cumulative from state
    if result.agent1_response:
        tokens = result.agent1_response.usage.total_tokens
        tool_calls = len(result.agent1_response.tool_calls_made)
        content.append(f"\nImplementer   {tokens:,} tokens, {tool_calls} tool calls")
    elif state:
        # Show cumulative metrics when cycle-specific ones aren't available
        tokens = state.total_agent1_usage.total_tokens
        content.append(f"\nImplementer   {tokens:,} tokens (cumulative)")

    if result.agent2_review:
        tokens = result.agent2_review.usage.total_tokens
        content.append(f"\nReviewer      {tokens:,} tokens")
    elif state:
        # Show cumulative metrics when cycle-specific ones aren't available
        tokens = state.total_agent2_usage.total_tokens
        content.append(f"\nReviewer      {tokens:,} tokens (cumulative)")
    
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


def multiline_input(prompt_text: str, hint: str = "") -> str:
    console.print()
    console.print(Panel(
        f"{prompt_text}\n\n[{COLORS['muted']}]{hint}[/]",
        border_style=COLORS["cyan"],
        box=box.ROUNDED,
    ))
    console.print()
    
    lines = []
    console.print(f"  [{COLORS['muted']}]Enter your text (empty line + Enter to finish):[/]")
    console.print()
    
    while True:
        try:
            line = prompt(
                HTML('<prompt>  │ </prompt>'),
                style=pt_style,
            )
            if line == "" and lines and lines[-1] == "":
                lines.pop()
                break
            lines.append(line)
        except EOFError:
            break
        except KeyboardInterrupt:
            return ""
    
    return "\n".join(lines)


def single_input(prompt_text: str, default: str = "") -> str:
    try:
        suffix = f" [{default}]" if default else ""
        result = prompt(
            HTML(f'<prompt>  {prompt_text}{suffix}: </prompt>'),
            style=pt_style,
            default="",
        )
        return result.strip() if result.strip() else default
    except (EOFError, KeyboardInterrupt):
        return default


class CompletenessREPL:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()
        self.config = LoopConfig()
        self.workspace: Optional[Path] = None
        self.idea_file: Optional[Path] = None
        self.orchestrator: Optional[Orchestrator] = None
        self.running = False
        self.history = InMemoryHistory()
        self.custom_instructions = ""
    
    def get_prompt_text(self):
        return HTML('<prompt>❯ </prompt>')
    
    def auto_detect(self) -> bool:
        self.idea_file = detect_idea_file(self.base_dir)
        if self.idea_file:
            self.workspace = setup_workspace(self.base_dir)
            return True
        return False
    
    def print_config(self):
        console.print()
        console.print(f"  [{COLORS['muted']}]Current Settings:[/]")
        console.print()
        
        idea_display = self.idea_file.name if self.idea_file else "[none]"
        workspace_display = str(self.workspace.relative_to(self.base_dir)) if self.workspace else "./workspace"
        instr_preview = self.custom_instructions[:35] + "..." if len(self.custom_instructions) > 35 else self.custom_instructions
        instr_display = instr_preview.replace("\n", " ") if self.custom_instructions else "[none]"
        
        console.print(f"  [{COLORS['cyan']}][1][/] Idea file     {idea_display}")
        console.print(f"  [{COLORS['cyan']}][2][/] Workspace     {workspace_display}")
        console.print(f"  [{COLORS['cyan']}][3][/] Backend       {self.config.model.backend}")
        console.print(f"  [{COLORS['cyan']}][4][/] Model         {self.config.model.name}")
        console.print(f"  [{COLORS['cyan']}][5][/] Max cycles    {self.config.limits.max_iterations}")
        console.print(f"  [{COLORS['cyan']}][6][/] Instructions  {instr_display}")
        console.print()
    
    def prompt_for_idea(self):
        console.print()
        print_error("No idea.md file found in current directory")
        console.print()
        
        idea_content = multiline_input(
            "Paste your project idea below",
            "Describe what you want to build. Be specific about features, technology, etc."
        )
        
        if idea_content.strip():
            self.base_dir.mkdir(parents=True, exist_ok=True)
            idea_path = self.base_dir / "idea.md"
            idea_path.write_text(idea_content)
            self.idea_file = idea_path
            self.workspace = setup_workspace(self.base_dir)
            print_success(f"Created {idea_path.name}")
            return True
        return False
    
    def prompt_for_instructions(self):
        console.print()
        self.custom_instructions = multiline_input(
            "Any custom instructions for the agent?",
            "Optional. Add coding style preferences, specific requirements, etc."
        )
        if self.custom_instructions:
            print_success("Custom instructions saved")
    
    def settings_menu(self):
        while True:
            self.print_config()
            console.print(f"  [{COLORS['cyan']}]Enter number to change, or press Enter to continue:[/]")
            console.print()
            
            try:
                choice = prompt(
                    HTML('<prompt>  ❯ </prompt>'),
                    style=pt_style,
                ).strip()
            except (EOFError, KeyboardInterrupt):
                break
            
            if not choice:
                break
            
            if choice == "1":
                if not self.idea_file:
                    self.prompt_for_idea()
                else:
                    console.print(f"  [{COLORS['muted']}]Current idea file: {self.idea_file}[/]")
                    if single_input("Replace it? (y/n)", "n").lower() == "y":
                        self.prompt_for_idea()
            
            elif choice == "2":
                new_ws = single_input("Workspace path", "./workspace")
                self.workspace = (self.base_dir / new_ws).resolve()
                print_success(f"Workspace: {self.workspace}")
            
            elif choice == "3":
                console.print(f"  [{COLORS['muted']}]API: anthropic, ollama, lmstudio, mlx, openai, mistral[/]")
                console.print(f"  [{COLORS['warning']}]CLI (⚠️ uses subscription credits): claude-cli, codex, gemini[/]")
                new_backend = single_input("Backend", self.config.model.backend)
                self.config.model.backend = new_backend
                print_success(f"Backend: {new_backend}")

                # Prompt for API key if switching to OpenAI or Anthropic
                if new_backend.lower() in ("openai", "gpt", "anthropic", "claude"):
                    self._prompt_for_api_key()
            
            elif choice == "4":
                # Provide model suggestions based on backend
                backend = self.config.model.backend.lower()
                if backend in ("claude-cli", "claude_cli", "claudecode", "claude-code"):
                    console.print(f"  [{COLORS['muted']}]Models: sonnet, opus, haiku[/]")
                elif backend in ("codex", "codex-cli", "openai-cli"):
                    console.print(f"  [{COLORS['muted']}]Models: gpt-5-codex, gpt-5, gpt-4o[/]")
                elif backend in ("gemini", "gemini-cli"):
                    console.print(f"  [{COLORS['muted']}]Models: gemini-2.5-flash, gemini-2.5-pro, gemini-3-pro[/]")
                elif backend in ("anthropic", "claude"):
                    console.print(f"  [{COLORS['muted']}]Models: claude-3-5-sonnet-20241022, claude-3-opus-20250219, claude-3-haiku-20240307[/]")
                elif backend in ("openai", "gpt"):
                    console.print(f"  [{COLORS['muted']}]Models: gpt-4o, gpt-4o-mini, gpt-4-turbo[/]")
                elif backend in ("mistral", "devstral"):
                    console.print(f"  [{COLORS['muted']}]Models: devstral-small-2505, mistral-large-latest[/]")

                new_model = single_input("Model name", self.config.model.name)
                self.config.model.name = new_model
                print_success(f"Model: {new_model}")
            
            elif choice == "5":
                new_max = single_input("Max cycles", str(self.config.limits.max_iterations))
                try:
                    self.config.limits.max_iterations = int(new_max)
                    print_success(f"Max cycles: {new_max}")
                except ValueError:
                    print_error("Invalid number")
            
            elif choice == "6":
                self.prompt_for_instructions()

    def _prompt_for_api_key(self):
        """Prompt user for API key based on the configured backend."""
        import os

        backend = self.config.model.backend.lower()

        if backend in ("anthropic", "claude"):
            env_var = "ANTHROPIC_API_KEY"
            config_key = "anthropic_api_key"
            service_name = "Anthropic"
            service_url = "https://console.anthropic.com/"
        elif backend in ("openai", "gpt"):
            env_var = "OPENAI_API_KEY"
            config_key = "openai_api_key"
            service_name = "OpenAI"
            service_url = "https://platform.openai.com/api-keys"
        else:
            return

        console.print()
        existing_key = os.environ.get(env_var) or getattr(self.config.model, config_key, None)

        if existing_key:
            masked_key = existing_key[:7] + "*" * (len(existing_key) - 11) + existing_key[-4:] if len(existing_key) > 11 else "*" * len(existing_key)
            console.print(f"  [{COLORS['muted']}]Current {service_name} key: {masked_key}[/]")
            if single_input("Use existing key? (y/n)", "y").lower() == "y":
                os.environ[env_var] = existing_key
                return

        console.print(f"  [{COLORS['muted']}]Your {service_name} API key is not shared or stored in plain text.[/]")
        api_key = single_input(f"Enter your {service_name} API key", "")

        if api_key.strip():
            setattr(self.config.model, config_key, api_key)
            os.environ[env_var] = api_key
            masked = api_key[:7] + "*" * (len(api_key) - 11) + api_key[-4:] if len(api_key) > 11 else "*" * len(api_key)
            print_success(f"{service_name} API key set: {masked}")
        else:
            print_error(f"API key is required for {service_name} backend")

    def cmd_go(self):
        if not self.idea_file:
            if not self.prompt_for_idea():
                print_error("Cannot start without a project idea")
                return
        
        if not self.workspace:
            self.workspace = setup_workspace(self.base_dir)
        
        self.settings_menu()
        
        if not self.idea_file:
            print_error("No idea file configured")
            return
        
        console.print()
        console.print(Panel(
            "Ready to start autonomous development?\n\n"
            f"[{COLORS['muted']}]The agent will read your idea and build the project.[/]\n"
            f"[{COLORS['muted']}]Press Ctrl+C anytime to pause.[/]",
            border_style=COLORS["cyan"],
            box=box.ROUNDED,
        ))
        console.print()
        
        confirm = single_input("Start building? (y/n)", "y")
        if confirm.lower() != "y":
            console.print(f"  [{COLORS['muted']}]Cancelled. Type 'go' to try again.[/]")
            return
        
        console.print()
        
        workspace = self.workspace
        with console.status("[bold blue]Setting up workspace...", spinner="dots"):
            workspace.mkdir(exist_ok=True)
            idea_in_workspace = copy_idea_to_workspace(self.idea_file, workspace)
            git_initialized = init_git(workspace)
        
        print_success(f"Workspace ready: {workspace}")
        if git_initialized:
            print_success("Git repository initialized")
        print_success(f"Project spec: {idea_in_workspace.name}")
        
        console.print()
        
        custom_part = ""
        if self.custom_instructions:
            custom_part = f"\n\nADDITIONAL INSTRUCTIONS:\n{self.custom_instructions}"
        
        initial_prompt = f"""Build the complete project described in @idea.md

Read the specification file carefully, then implement everything it describes.
Work systematically through all requirements.
Create proper project structure, write clean code, and ensure it runs correctly.
Commit your progress after completing each major feature.{custom_part}

Start now."""
        
        self._run_loop(self.idea_file, workspace, initial_prompt=initial_prompt)
    
    def cmd_resume(self):
        if not self.workspace:
            self.workspace = setup_workspace(self.base_dir)
        
        state_file = self.workspace / ".completeness_state.json"
        if not state_file.exists():
            print_error("No saved session to resume")
            console.print(f"  [{COLORS['muted']}]Use 'go' to start a new session[/]")
            return
        
        if not self.idea_file:
            self.idea_file = detect_idea_file(self.base_dir) or (self.workspace / "idea.md")
        
        self._run_loop(self.idea_file, self.workspace, resume=True)
    
    def _run_loop(self, idea_path: Path, workspace_path: Path, resume: bool = False, initial_prompt: str = ""):
        start_time = time.time()
        
        def on_cycle(result: CycleResult):
            phase = self.orchestrator.state.phase if self.orchestrator else "implementation"
            state = self.orchestrator.state if self.orchestrator else None
            print_cycle_result(result, phase, state)
        
        def on_status(status: str):
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
            self.workspace = setup_workspace(self.base_dir)
        
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
            self.workspace = setup_workspace(self.base_dir)
        
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
    
    def print_help(self):
        help_text = """[bold]Commands:[/]
  [cyan]go[/]           Start or configure a new session
  [cyan]resume[/]       Resume a paused session
  [cyan]status[/]       Show current progress
  [cyan]history[/]      Show completeness score history
  [cyan]settings[/]     Change configuration
  [cyan]backends[/]     List available LLM backends
  [cyan]help[/]         Show this help
  [cyan]quit[/]         Exit"""
        console.print(Panel(help_text, border_style=COLORS["muted"], box=box.ROUNDED, title="Help"))
    
    def run(self):
        print_banner()
        
        found_idea = self.auto_detect()
        
        if found_idea:
            self.print_config()
            console.print(f"  [{COLORS['cyan']}]Type 'go' to configure and start, or 'help' for options[/]")
        else:
            console.print()
            console.print(f"  [{COLORS['muted']}]No idea.md found. Type 'go' to create one.[/]")
        
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
            elif cmd == "settings":
                self.settings_menu()
            elif cmd == "backends":
                self.cmd_backends()
            elif cmd == "config":
                self.cmd_config()
            elif cmd == "help":
                self.print_help()
            else:
                print_error(f"Unknown command: {cmd}")
                console.print(f"  [{COLORS['muted']}]Type 'help' for available commands[/]")
        
        console.print()
        console.print(f"[{COLORS['muted']}]Goodbye![/]")
        console.print()


def main():
    base_dir = Path.cwd()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        base_dir = Path(sys.argv[1]).resolve()
    
    repl = CompletenessREPL(base_dir)
    repl.run()


if __name__ == "__main__":
    main()
