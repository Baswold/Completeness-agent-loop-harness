import time
import json
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import subprocess

from .config import (
    LoopConfig,
    DEFAULT_AGENT1_PROMPT,
    DEFAULT_AGENT2_IMPLEMENTATION_PROMPT,
    DEFAULT_AGENT2_TESTING_PROMPT
)
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
    phase: str = "implementation"
    
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
            "start_time": self.start_time,
            "phase": self.phase
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LoopState":
        state = cls()
        state.cycle_count = data.get("cycle_count", 0)
        state.completeness_history = data.get("completeness_history", [])
        state.is_paused = data.get("is_paused", False)
        state.is_complete = data.get("is_complete", False)
        state.start_time = data.get("start_time")
        state.phase = data.get("phase", "implementation")
        
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
        self.context_builder = ContextBuilder(
            workspace,
            original_spec_name=idea_file.name if idea_file else "idea.md"
        )
        
        agent1_prompt = config.agents.agent1_system_prompt
        if agent1_prompt and Path(agent1_prompt).exists():
            agent1_prompt = Path(agent1_prompt).read_text()
        else:
            agent1_prompt = DEFAULT_AGENT1_PROMPT
        
        agent2_impl_prompt = config.agents.agent2_implementation_prompt
        if agent2_impl_prompt and Path(agent2_impl_prompt).exists():
            agent2_impl_prompt = Path(agent2_impl_prompt).read_text()
        else:
            agent2_impl_prompt = DEFAULT_AGENT2_IMPLEMENTATION_PROMPT
        
        agent2_test_prompt = config.agents.agent2_testing_prompt
        if agent2_test_prompt and Path(agent2_test_prompt).exists():
            agent2_test_prompt = Path(agent2_test_prompt).read_text()
        else:
            agent2_test_prompt = DEFAULT_AGENT2_TESTING_PROMPT
        
        self.agent1 = Agent1(self.llm, self.tools, agent1_prompt)
        self.agent2_implementation = Agent2(self.llm, agent2_impl_prompt)
        self.agent2_testing = Agent2(self.llm, agent2_test_prompt)
        self.testing_threshold = config.agents.testing_phase_threshold
        
        self.original_spec = idea_file.read_text() if idea_file.exists() else ""
    
    def _get_agent2(self) -> Agent2:
        if self.state.phase == "testing":
            return self.agent2_testing
        return self.agent2_implementation
    
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

    def _execute_git_commit(self, commit_instructions: str):
        """
        Execute git commit based on Agent 2's instructions.
        
        This implements the automatic commit strategy where Agent 2 specifies
        exactly what should be committed, and Agent 1 executes it.
        
        Includes commit message sanitization to prevent Agent 1 bias by:
        1. Removing subjective claims of completeness
        2. Focusing on factual changes only
        3. Standardizing commit message format
        """
        if not commit_instructions:
            return
            
        try:
            # Parse commit instructions to extract files and message
            lines = commit_instructions.split('\n')
            files_to_add = []
            commit_message = ""
            
            in_commit_section = False
            for line in lines:
                if line.startswith('git add'):
                    # Extract files from git add command
                    parts = line.split()
                    if len(parts) >= 3:
                        files_to_add.extend(parts[2:])
                elif line.startswith('git commit'):
                    in_commit_section = True
                elif in_commit_section and ('-m "' in line or '-m \"' in line):
                    # Extract commit message (handle both single and double quotes)
                    if '-m "' in line:
                        message_start = line.find('"') + 1
                        # Look for closing quote in subsequent lines
                        commit_message = line[message_start:]
                        i = lines.index(line) + 1
                        while i < len(lines) and '"' not in lines[i]:
                            commit_message += '\n' + lines[i]
                            i += 1
                        if i < len(lines):
                            commit_message += lines[i][:lines[i].find('"')]
                    elif "-m \"" in line:
                        message_start = line.find("\"") + 1
                        # Look for closing quote in subsequent lines
                        commit_message = line[message_start:]
                        i = lines.index(line) + 1
                        while i < len(lines) and "\"" not in lines[i]:
                            commit_message += '\n' + lines[i]
                            i += 1
                        if i < len(lines):
                            commit_message += lines[i][:lines[i].find("\"")]
                    break
            
            if not files_to_add:
                # Default to adding all changes
                files_to_add = ['.']
            
            if commit_message:
                # COMMIT MESSAGE SANITIZATION: Remove Agent 1 bias
                sanitized_message = self._sanitize_commit_message(commit_message)
                
                # Execute git add
                for file_path in files_to_add:
                    self.tools.execute('git_add', {'paths': [file_path]})
                
                # Execute git commit with sanitized message
                result = self.tools.execute('git_commit', {'message': sanitized_message})
                
                if result.success:
                    self._update_status(f"Git commit executed: {sanitized_message[:50]}...")
                else:
                    self._update_status(f"Git commit failed: {result.error}")
                    
        except Exception as e:
            self._update_status(f"Error executing git commit: {str(e)}")

    def _sanitize_commit_message(self, message: str) -> str:
        """
        Sanitize commit message to remove Agent 1 bias and subjective claims.
        
        This prevents Agent 1 from influencing Agent 2 through commit messages
        by removing claims like "fully implemented" or "complete" that might
        not be accurate.
        """
        # Remove subjective claims of completeness (case insensitive)
        import re
        bias_phrases = [
            r'fully implemented', r'completely implemented', r'fully complete',
            r'comprehensive', r'thorough', r'complete solution', r'perfect',
            r'all edge cases', r'all requirements', r'everything working',
            r'production ready', r'fully tested', r'comprehensive testing'
        ]
        
        sanitized = message
        for phrase in bias_phrases:
            sanitized = re.sub(phrase, '', sanitized, flags=re.IGNORECASE)
        
        # Remove multiple spaces and clean up
        sanitized = ' '.join(sanitized.split())
        
        # Ensure message is not empty after sanitization
        if not sanitized.strip():
            sanitized = "Auto-commit: code changes"
        
        # Add completeness score from state if available
        if self.state.completeness_history:
            latest_score = self.state.completeness_history[-1]["score"]
            sanitized = f"[{self.state.phase}] {sanitized}\
\nCompleteness: {latest_score}%"
        
        return sanitized

    def _run_tests_before_commit(self) -> Optional[str]:
        """
        Run tests before committing to ensure code quality.
        Returns test results if tests exist, None otherwise.
        """
        try:
            # Use the context builder to run tests
            test_results = self.context_builder.run_tests()
            
            if test_results and "No tests found" not in test_results:
                # Log test results
                test_summary = self._analyze_test_results(test_results)
                self._update_status(f"Tests run: {test_summary}")
                return test_results
            else:
                self._update_status("No tests found - proceeding without test verification")
                return None
                
        except Exception as e:
            self._update_status(f"Test execution failed: {str(e)}")
            return None

    def _analyze_test_results(self, test_results: str) -> str:
        """
        Analyze test results to determine pass/fail status.
        """
        lines = test_results.lower()
        
        if "passed" in lines and "failed" in lines:
            # Try to extract numbers
            import re
            passed_match = re.search(r'(\d+) passed', lines)
            failed_match = re.search(r'(\d+) failed', lines)
            
            if passed_match and failed_match:
                passed = int(passed_match.group(1))
                failed = int(failed_match.group(1))
                return f"{passed} passed, {failed} failed"
        
        elif "passed" in lines:
            return "All tests passed"
        elif "failed" in lines or "error" in lines:
            return "Tests failed"
        
        return "Tests executed"

    def _should_commit_based_on_tests(self, test_results: str, review: ReviewResult) -> bool:
        """
        Decide whether to commit based on test results and current phase.
        
        Strategy:
        - In testing phase: Always commit (Agent 2 will review test failures)
        - In implementation phase: Only commit if tests pass or no tests exist
        """
        if self.state.phase == "testing":
            # In testing phase, always commit so Agent 2 can review test failures
            return True
        
        # In implementation phase, check if tests pass
        lines = test_results.lower()
        
        # If tests explicitly passed, commit
        if ("passed" in lines and "failed" not in lines) or "all tests passed" in lines:
            return True
        
        # If tests failed, don't commit
        if "failed" in lines or "error" in lines:
            return False
        
        # If unclear, commit anyway (better to have Agent 2 review)
        return True
    
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
            error_msg = f"Agent 1 error: {str(e)}"
            self._update_status(error_msg)
            
            # Add error to state for recovery
            self.state.last_review = ReviewResult(
                raw_content=f"Error occurred: {str(e)}",
                completeness_score=self.state.completeness_history[-1]["score"] if self.state.completeness_history else 0,
                completed_items=[],
                remaining_work=[f"Recover from error: {str(e)}"],
                issues_found=[f"Agent 1 failed: {str(e)}"],
                commit_instructions="",
                next_instructions=f"Agent 1 encountered an error: {str(e)}. Please try to recover and continue the task.",
                usage=TokenUsage(),
                is_complete=False
            )
            
            return CycleResult(
                cycle_number=cycle_num,
                agent1_response=None,
                agent2_review=self.state.last_review,
                completeness_score=self.state.last_review.completeness_score,
                is_complete=False,
                error=error_msg,
                duration_seconds=time.time() - cycle_start
            )
        
        phase_label = "testing" if self.state.phase == "testing" else "implementation"
        self._update_status(f"Cycle {cycle_num}: Agent 2 reviewing ({phase_label})...")
        
        # CRITICAL ISOLATION: Agent 2 context is built ONLY from filesystem state.
        # Agent 1's response (agent1_response) is NEVER passed to Agent 2.
        # This prevents same-model bias where Agent 2 might be persuaded by
        # Agent 1's confident-but-wrong self-assessments.
        # Agent 2 reviews ONLY: original spec + current codebase + git log
        codebase_for_review = self.context_builder.build_agent2_context()
        git_log = self.context_builder.get_git_log()
        
        try:
            # Note: agent1_response is intentionally NOT passed here
            # Uses phase-appropriate Agent 2 (implementation or testing reviewer)
            agent2 = self._get_agent2()
            review = agent2.review(
                original_spec=self.original_spec,
                codebase_context=codebase_for_review,
                git_log=git_log
            )
            self.state.total_agent2_usage = self.state.total_agent2_usage + review.usage
            self.state.last_review = review
        except Exception as e:
            error_msg = f"Agent 2 error: {str(e)}"
            self._update_status(error_msg)
            
            # Create fallback review to continue progress
            fallback_review = ReviewResult(
                raw_content=f"Agent 2 review failed: {str(e)}",
                completeness_score=self.state.completeness_history[-1]["score"] if self.state.completeness_history else 0,
                completed_items=[],
                remaining_work=["Continue implementation - Agent 2 review failed"],
                issues_found=[f"Review failed: {str(e)}"],
                commit_instructions="",
                next_instructions="Agent 2 encountered an error. Continue with the current task based on the original specification.",
                usage=TokenUsage(),
                is_complete=False
            )
            
            self.state.last_review = fallback_review
            
            return CycleResult(
                cycle_number=cycle_num,
                agent1_response=agent1_response,
                agent2_review=fallback_review,
                completeness_score=fallback_review.completeness_score,
                is_complete=False,
                error=error_msg,
                duration_seconds=time.time() - cycle_start
            )
        
        self.state.completeness_history.append({
            "cycle": cycle_num,
            "score": review.completeness_score,
            "timestamp": datetime.now().isoformat(),
            "phase": self.state.phase
        })
        
        # Execute git commit if Agent 2 provided instructions
        # But first, run tests to ensure changes don't break anything
        test_results = self._run_tests_before_commit()
        
        if test_results:
            # Only commit if tests pass or if this is the testing phase
            should_commit = self._should_commit_based_on_tests(test_results, review)
            if should_commit:
                self._execute_git_commit(review.commit_instructions)
            else:
                self._update_status("Skipping commit: tests are failing")
        else:
            # No tests found, proceed with commit
            self._execute_git_commit(review.commit_instructions)

        # Phase transition: switch to testing phase when threshold is reached
        if self.state.phase == "implementation" and review.completeness_score >= self.testing_threshold:
            self.state.phase = "testing"
            self._update_status(f"Phase transition: Switching to TESTING mode (score: {review.completeness_score}%)")
        
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

        max_consecutive_errors = 3  # Stop after 3 consecutive errors
        consecutive_errors = 0
        
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
                consecutive_errors += 1
                self._update_status(f"Error in cycle {result.cycle_number}: {result.error}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self._update_status(f"Stopping after {max_consecutive_errors} consecutive errors")
                    break
                
                # Short delay before retry
                time.sleep(5)
            else:
                consecutive_errors = 0  # Reset error counter on success
        
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
            "phase": self.state.phase,
            "elapsed_seconds": elapsed,
            "current_score": self.state.completeness_history[-1]["score"] if self.state.completeness_history else 0,
            "agent1_tokens": self.state.total_agent1_usage.total_tokens,
            "agent2_tokens": self.state.total_agent2_usage.total_tokens,
            "total_tokens": self.state.total_agent1_usage.total_tokens + self.state.total_agent2_usage.total_tokens
        }
