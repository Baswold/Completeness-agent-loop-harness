import time
import json
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import subprocess

from .config import LoopConfig, DEFAULT_AGENT1_PROMPT, DEFAULT_AGENT2_PROMPT
from .llm import create_backend, TokenUsage
from .tools import ToolRegistry
from .agents import Agent1, Agent2, ReviewResult, AgentResponse
from .context import ContextBuilder


@dataclass
class CycleResult:
    cycle_number: int
    agent1_response: Optional[AgentResponse]
    agent2_review: Optional[ReviewResult]
    completeness_score: int
    is_complete: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class LoopState:
    cycle_count: int = 0
    total_agent1_usage: TokenUsage = field(default_factory=TokenUsage)
    total_agent2_usage: TokenUsage = field(default_factory=TokenUsage)
    completeness_history: list = field(default_factory=list)
    is_paused: bool = False
    is_complete: bool = False
    start_time: Optional[float] = None
    last_review: Optional[ReviewResult] = None
    
    def to_dict(self) -> dict:
        return {
            "cycle_count": self.cycle_count,
            "total_agent1_usage": {
                "prompt_tokens": self.total_agent1_usage.prompt_tokens,
                "completion_tokens": self.total_agent1_usage.completion_tokens,
                "total_tokens": self.total_agent1_usage.total_tokens
            },
            "total_agent2_usage": {
                "prompt_tokens": self.total_agent2_usage.prompt_tokens,
                "completion_tokens": self.total_agent2_usage.completion_tokens,
                "total_tokens": self.total_agent2_usage.total_tokens
            },
            "completeness_history": self.completeness_history,
            "is_paused": self.is_paused,
            "is_complete": self.is_complete,
            "start_time": self.start_time
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LoopState":
        state = cls()
        state.cycle_count = data.get("cycle_count", 0)
        state.completeness_history = data.get("completeness_history", [])
        state.is_paused = data.get("is_paused", False)
        state.is_complete = data.get("is_complete", False)
        state.start_time = data.get("start_time")
        
        a1_usage = data.get("total_agent1_usage", {})
        state.total_agent1_usage = TokenUsage(
            prompt_tokens=a1_usage.get("prompt_tokens", 0),
            completion_tokens=a1_usage.get("completion_tokens", 0),
            total_tokens=a1_usage.get("total_tokens", 0)
        )
        
        a2_usage = data.get("total_agent2_usage", {})
        state.total_agent2_usage = TokenUsage(
            prompt_tokens=a2_usage.get("prompt_tokens", 0),
            completion_tokens=a2_usage.get("completion_tokens", 0),
            total_tokens=a2_usage.get("total_tokens", 0)
        )
        
        return state


class Orchestrator:
    def __init__(
        self,
        workspace: Path,
        idea_file: Path,
        config: LoopConfig,
        on_cycle_complete: Optional[Callable[[CycleResult], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None
    ):
        self.workspace = workspace
        self.idea_file = idea_file
        self.config = config
        self.on_cycle_complete = on_cycle_complete
        self.on_status_change = on_status_change
        
        self.state = LoopState()
        self.state_file = workspace / ".completeness_state.json"
        
        self.llm = create_backend(config)
        self.tools = ToolRegistry(workspace)
        self.context_builder = ContextBuilder(workspace)
        
        agent1_prompt = config.agents.agent1_system_prompt
        if agent1_prompt and Path(agent1_prompt).exists():
            agent1_prompt = Path(agent1_prompt).read_text()
        else:
            agent1_prompt = DEFAULT_AGENT1_PROMPT
        
        agent2_prompt = config.agents.agent2_system_prompt
        if agent2_prompt and Path(agent2_prompt).exists():
            agent2_prompt = Path(agent2_prompt).read_text()
        else:
            agent2_prompt = DEFAULT_AGENT2_PROMPT
        
        self.agent1 = Agent1(self.llm, self.tools, agent1_prompt)
        self.agent2 = Agent2(self.llm, agent2_prompt)
        
        self.original_spec = idea_file.read_text() if idea_file.exists() else ""
    
    def _update_status(self, status: str):
        if self.on_status_change:
            self.on_status_change(status)
    
    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)
    
    def _load_state(self) -> bool:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                self.state = LoopState.from_dict(data)
                return True
            except Exception:
                pass
        return False
    
    def _init_git(self):
        git_dir = self.workspace / ".git"
        if not git_dir.exists():
            subprocess.run(
                ["git", "init"],
                cwd=self.workspace,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "completeness-loop@local"],
                cwd=self.workspace,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.name", "Completeness Loop"],
                cwd=self.workspace,
                capture_output=True
            )
    
    def run_cycle(self) -> CycleResult:
        cycle_start = time.time()
        self.state.cycle_count += 1
        cycle_num = self.state.cycle_count
        
        self._update_status(f"Cycle {cycle_num}: Agent 1 implementing...")
        
        if self.state.last_review:
            instructions = self.state.last_review.next_instructions
        else:
            instructions = f"""This is the initial implementation cycle.

Read the specification carefully and begin implementing the project.
Start with the core structure and work incrementally.

SPECIFICATION:
{self.original_spec}

Begin implementation now.
"""
        
        codebase_context = self.context_builder.build_agent1_context()
        last_commit = self.context_builder.get_last_commit()
        
        task_summary = self.original_spec[:500] + "..." if len(self.original_spec) > 500 else self.original_spec
        
        try:
            agent1_response = self.agent1.run(
                instructions=instructions,
                codebase_context=codebase_context,
                last_commit=last_commit,
                task_summary=task_summary
            )
            self.state.total_agent1_usage = self.state.total_agent1_usage + agent1_response.usage
        except Exception as e:
            return CycleResult(
                cycle_number=cycle_num,
                agent1_response=None,
                agent2_review=None,
                completeness_score=0,
                is_complete=False,
                error=f"Agent 1 error: {str(e)}",
                duration_seconds=time.time() - cycle_start
            )
        
        self._update_status(f"Cycle {cycle_num}: Agent 2 reviewing...")
        
        # CRITICAL ISOLATION: Agent 2 context is built ONLY from filesystem state.
        # Agent 1's response (agent1_response) is NEVER passed to Agent 2.
        # This prevents same-model bias where Agent 2 might be persuaded by
        # Agent 1's confident-but-wrong self-assessments.
        # Agent 2 reviews ONLY: original spec + current codebase + git log
        codebase_for_review = self.context_builder.build_agent2_context()
        git_log = self.context_builder.get_git_log()
        
        try:
            # Note: agent1_response is intentionally NOT passed here
            review = self.agent2.review(
                original_spec=self.original_spec,
                codebase_context=codebase_for_review,
                git_log=git_log
            )
            self.state.total_agent2_usage = self.state.total_agent2_usage + review.usage
            self.state.last_review = review
        except Exception as e:
            return CycleResult(
                cycle_number=cycle_num,
                agent1_response=agent1_response,
                agent2_review=None,
                completeness_score=0,
                is_complete=False,
                error=f"Agent 2 error: {str(e)}",
                duration_seconds=time.time() - cycle_start
            )
        
        self.state.completeness_history.append({
            "cycle": cycle_num,
            "score": review.completeness_score,
            "timestamp": datetime.now().isoformat()
        })
        
        if review.is_complete:
            self.state.is_complete = True
        
        self._save_state()
        
        result = CycleResult(
            cycle_number=cycle_num,
            agent1_response=agent1_response,
            agent2_review=review,
            completeness_score=review.completeness_score,
            is_complete=review.is_complete,
            duration_seconds=time.time() - cycle_start
        )
        
        if self.on_cycle_complete:
            self.on_cycle_complete(result)
        
        return result
    
    def run(self, resume: bool = False) -> LoopState:
        if resume and self._load_state():
            self._update_status("Resuming from saved state...")
        else:
            self.state = LoopState()
            self.state.start_time = time.time()
        
        self._init_git()
        
        max_iterations = self.config.limits.max_iterations
        max_runtime = self.config.limits.max_runtime_hours * 3600
        
        while not self.state.is_complete and not self.state.is_paused:
            if self.state.cycle_count >= max_iterations:
                self._update_status(f"Reached max iterations ({max_iterations})")
                break
            
            elapsed = time.time() - (self.state.start_time or time.time())
            if elapsed >= max_runtime:
                self._update_status(f"Reached max runtime ({self.config.limits.max_runtime_hours}h)")
                break
            
            result = self.run_cycle()
            
            if result.error:
                self._update_status(f"Error in cycle {result.cycle_number}: {result.error}")
                time.sleep(5)
        
        self._save_state()
        return self.state
    
    def pause(self):
        self.state.is_paused = True
        self._save_state()
        self._update_status("Loop paused")
    
    def get_status(self) -> dict:
        elapsed = 0
        if self.state.start_time:
            elapsed = time.time() - self.state.start_time
        
        return {
            "cycle_count": self.state.cycle_count,
            "is_complete": self.state.is_complete,
            "is_paused": self.state.is_paused,
            "elapsed_seconds": elapsed,
            "current_score": self.state.completeness_history[-1]["score"] if self.state.completeness_history else 0,
            "agent1_tokens": self.state.total_agent1_usage.total_tokens,
            "agent2_tokens": self.state.total_agent2_usage.total_tokens,
            "total_tokens": self.state.total_agent1_usage.total_tokens + self.state.total_agent2_usage.total_tokens
        }
