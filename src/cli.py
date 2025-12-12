import click
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
import threading
import signal
import sys

from .config import LoopConfig
from .orchestrator import Orchestrator, CycleResult
from .llm import list_backends


BANNER = r"""
   ____                      _      _                            _                      
  / ___|___  _ __ ___  _ __ | | ___| |_ ___ _ __   ___  ___ ___  | |    ___   ___  _ __  
 | |   / _ \| '_ ` _ \| '_ \| |/ _ \ __/ _ \ '_ \ / _ \/ __/ __| | |   / _ \ / _ \| '_ \ 
 | |__| (_) | | | | | | |_) | |  __/ ||  __/ | | |  __/\__ \__ \ | |__| (_) | (_) | |_) |
  \____\___/|_| |_| |_| .__/|_|\___|\__\___|_| |_|\___||___/___/ |_____\___/ \___/| .__/ 
                      |_|                                                         |_|    
"""

SMALL_BANNER = """
================================================================================
                         COMPLETENESS AGENT LOOP
                    Autonomous Multi-Agent Coding System
================================================================================
"""


def print_header():
    print(SMALL_BANNER)


def print_separator(char="-", width=80):
    print(char * width)


def print_progress_bar(score: int, width: int = 40) -> str:
    filled = int(score / 100 * width)
    empty = width - filled
    bar = "#" * filled + "-" * empty
    return f"[{bar}] {score}%"


def format_duration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def print_cycle_result(result: CycleResult, elapsed: float):
    print()
    print_separator("=")
    print(f"  CYCLE {result.cycle_number} COMPLETE")
    print_separator("=")
    print()
    
    print(f"  Completeness Score: {print_progress_bar(result.completeness_score)}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    print(f"  Total Elapsed:      {format_duration(elapsed)}")
    print()
    
    if result.agent1_response:
        a1_tokens = result.agent1_response.usage.total_tokens
        a1_iterations = result.agent1_response.iterations
        print(f"  Agent 1: {a1_tokens:,} tokens, {a1_iterations} iterations")
        print(f"           {len(result.agent1_response.tool_calls_made)} tool calls made")
    
    if result.agent2_review:
        a2_tokens = result.agent2_review.usage.total_tokens
        print(f"  Agent 2: {a2_tokens:,} tokens")
        print()
        
        if result.agent2_review.completed_items:
            print("  Completed:")
            for item in result.agent2_review.completed_items[:5]:
                print(f"    + {item[:60]}")
        
        if result.agent2_review.remaining_work:
            print("  Remaining:")
            for item in result.agent2_review.remaining_work[:5]:
                print(f"    - {item[:60]}")
        
        if result.agent2_review.issues_found:
            print("  Issues:")
            for issue in result.agent2_review.issues_found[:3]:
                print(f"    ! {issue[:60]}")
    
    if result.error:
        print()
        print(f"  ERROR: {result.error}")
    
    print()
    print_separator("-")


def print_status(status: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {status}")


def print_final_summary(status: dict, start_time: float):
    elapsed = time.time() - start_time
    
    print()
    print_separator("=")
    print("  SESSION COMPLETE")
    print_separator("=")
    print()
    print(f"  Total Cycles:    {status['cycle_count']}")
    print(f"  Final Score:     {print_progress_bar(status['current_score'])}")
    print(f"  Total Runtime:   {format_duration(elapsed)}")
    print()
    print(f"  Agent 1 Tokens:  {status['agent1_tokens']:,}")
    print(f"  Agent 2 Tokens:  {status['agent2_tokens']:,}")
    print(f"  Total Tokens:    {status['total_tokens']:,}")
    print()
    
    if status['is_complete']:
        print("  Status: COMPLETE - Project finished successfully!")
    elif status.get('is_paused'):
        print("  Status: PAUSED - Resume with --resume flag")
    else:
        print("  Status: STOPPED - Max iterations or runtime reached")
    
    print()
    print_separator("=")


@click.group()
def cli():
    """Completeness Loop - Autonomous Multi-Agent Coding System"""
    pass


@cli.command()
@click.option("--idea", "-i", required=True, type=click.Path(exists=True), help="Path to idea.md specification file")
@click.option("--workspace", "-w", required=True, type=click.Path(), help="Path to workspace directory")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config.yaml file")
@click.option("--resume", "-r", is_flag=True, help="Resume from saved state")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
def start(idea: str, workspace: str, config: str, resume: bool, quiet: bool):
    """Start or resume a completeness loop task"""
    idea_path = Path(idea).resolve()
    workspace_path = Path(workspace).resolve()
    
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    if config:
        loop_config = LoopConfig.load(Path(config))
    else:
        loop_config = LoopConfig()
    
    if not quiet:
        print_header()
        print()
        print(f"  Idea File:  {idea_path}")
        print(f"  Workspace:  {workspace_path}")
        print(f"  Backend:    {loop_config.model.backend}")
        print(f"  Model:      {loop_config.model.name}")
        print(f"  Max Cycles: {loop_config.limits.max_iterations}")
        print()
        print_separator()
    
    start_time = time.time()
    stop_event = threading.Event()
    
    def on_cycle_complete(result: CycleResult):
        if not quiet:
            elapsed = time.time() - start_time
            print_cycle_result(result, elapsed)
    
    def on_status_change(status: str):
        if not quiet:
            print_status(status)
    
    orchestrator = Orchestrator(
        workspace=workspace_path,
        idea_file=idea_path,
        config=loop_config,
        on_cycle_complete=on_cycle_complete,
        on_status_change=on_status_change
    )
    
    def signal_handler(sig, frame):
        print()
        print_status("Received interrupt signal. Pausing...")
        orchestrator.pause()
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    if not quiet:
        if resume:
            print_status("Resuming from saved state...")
        else:
            print_status("Starting new session...")
        print()
    
    try:
        orchestrator.run(resume=resume)
    except KeyboardInterrupt:
        orchestrator.pause()
    except Exception as e:
        print(f"\nERROR: {str(e)}")
    
    status = orchestrator.get_status()
    if not quiet:
        print_final_summary(status, start_time)


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
def status(workspace: str):
    """Check status of a running or completed loop"""
    workspace_path = Path(workspace).resolve()
    state_file = workspace_path / ".completeness_state.json"
    
    if not state_file.exists():
        print("ERROR: No state file found. Loop may not have been started.")
        return
    
    with open(state_file) as f:
        state = json.load(f)
    
    print()
    print_separator("=")
    print("  LOOP STATUS")
    print_separator("=")
    print()
    
    print(f"  Workspace:      {workspace_path}")
    print(f"  Cycles:         {state.get('cycle_count', 0)}")
    print(f"  Complete:       {'Yes' if state.get('is_complete') else 'No'}")
    print(f"  Paused:         {'Yes' if state.get('is_paused') else 'No'}")
    
    history = state.get("completeness_history", [])
    if history:
        latest = history[-1]
        print(f"  Latest Score:   {print_progress_bar(latest.get('score', 0))}")
    
    a1_usage = state.get("total_agent1_usage", {})
    a2_usage = state.get("total_agent2_usage", {})
    total = a1_usage.get('total_tokens', 0) + a2_usage.get('total_tokens', 0)
    
    print()
    print(f"  Agent 1 Tokens: {a1_usage.get('total_tokens', 0):,}")
    print(f"  Agent 2 Tokens: {a2_usage.get('total_tokens', 0):,}")
    print(f"  Total Tokens:   {total:,}")
    print()
    print_separator("=")


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
@click.option("--tail", "-n", default=20, help="Number of log entries to show")
def logs(workspace: str, tail: int):
    """View recent activity logs"""
    workspace_path = Path(workspace).resolve()
    log_file = workspace_path / "completeness_loop.log"
    
    if not log_file.exists():
        print("No log file found.")
        return
    
    with open(log_file) as f:
        lines = f.readlines()
    
    print()
    print_separator("=")
    print(f"  ACTIVITY LOG (last {tail} entries)")
    print_separator("=")
    print()
    
    for line in lines[-tail:]:
        print(f"  {line.rstrip()}")
    
    print()
    print_separator("=")


@cli.command()
@click.option("--workspace", "-w", required=True, type=click.Path(exists=True), help="Path to workspace directory")
def score(workspace: str):
    """Check current completeness score and history"""
    workspace_path = Path(workspace).resolve()
    state_file = workspace_path / ".completeness_state.json"
    
    if not state_file.exists():
        print("ERROR: No state file found.")
        return
    
    with open(state_file) as f:
        state = json.load(f)
    
    history = state.get("completeness_history", [])
    
    if not history:
        print("No completeness history yet.")
        return
    
    print()
    print_separator("=")
    print("  COMPLETENESS HISTORY")
    print_separator("=")
    print()
    print("  Cycle  | Score                                      | Timestamp")
    print("  -------+--------------------------------------------+--------------------")
    
    for entry in history[-20:]:
        cycle = entry.get("cycle", "?")
        score_val = entry.get("score", 0)
        timestamp = entry.get("timestamp", "")[:19]
        bar = print_progress_bar(score_val, 30)
        print(f"  {cycle:>5}  | {bar:<42} | {timestamp}")
    
    print()
    
    latest = history[-1].get("score", 0)
    print(f"  Current: {print_progress_bar(latest, 50)}")
    print()
    print_separator("=")


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output path for config file")
def init_config(output: str):
    """Generate a default configuration file"""
    config = LoopConfig()
    output_path = Path(output) if output else Path("config.yaml")
    config.save(output_path)
    print(f"Configuration saved to {output_path}")


@cli.command()
def backends():
    """Show available LLM backends and setup instructions"""
    print(list_backends())


def main():
    cli()


if __name__ == "__main__":
    main()
