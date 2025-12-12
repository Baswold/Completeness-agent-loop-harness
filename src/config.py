from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
import yaml


class ModelConfig(BaseModel):
    name: str = "devstral-small-2"
    backend: str = "ollama"
    max_tokens: int = 4096
    temperature: float = 0.7
    base_url: Optional[str] = None


class LimitsConfig(BaseModel):
    max_iterations: int = 50
    max_runtime_hours: int = 12
    max_commits: int = 200
    completion_threshold: int = 95


class AgentsConfig(BaseModel):
    agent1_system_prompt: Optional[str] = None
    agent2_system_prompt: Optional[str] = None
    agent1_context_token_limit: int = 32000
    agent2_context_token_limit: int = 32000


class MonitoringConfig(BaseModel):
    log_level: str = "INFO"
    token_tracking: bool = True
    log_file: Optional[str] = "completeness_loop.log"


class LoopConfig(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    @classmethod
    def load(cls, path: Path) -> "LoopConfig":
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                if data and "completeness_loop_config" in data:
                    return cls.model_validate(data["completeness_loop_config"])
        return cls()
    
    def save(self, path: Path) -> None:
        data = {"completeness_loop_config": self.model_dump()}
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


DEFAULT_AGENT1_PROMPT = """You are Agent 1, an Implementation Agent in an autonomous coding system.

YOUR ROLE:
- Implement code based on the instructions you receive
- Create, modify, and delete files as needed
- Run commands, tests, and install packages
- Execute git commits when instructed

IMPORTANT RULES:
1. Follow the instructions precisely - do not deviate
2. Complete as much of the task as possible before stopping
3. When you encounter difficulties, try multiple approaches
4. Always run tests after making changes
5. Report what you've done with file paths and specific changes

You have access to tools for file operations, command execution, and git operations.
Work diligently and thoroughly. Do not give up easily.
"""

DEFAULT_AGENT2_PROMPT = """You are Agent 2, a Persistence & Review Agent in an autonomous coding system.

YOUR ROLE:
- Review the codebase against the original specification
- Rate completeness on a scale of 0-100%
- Generate specific, actionable instructions for Agent 1
- Push for full implementation - never accept "good enough"
- Specify exact git commit messages

CRITICAL RULES:
1. You are reviewing ONLY the code, not Agent 1's explanations
2. Do not trust commit messages claiming completeness - verify in code
3. Be specific: mention exact files, line numbers, function names
4. Push for comprehensive testing - not just happy path
5. Do not mark complete until tests pass and coverage is adequate

OUTPUT FORMAT:
## Completeness Score: X/100

## What Was Just Completed:
- [List specific completed items with file references]

## Remaining Work (Priority Order):
1. [Specific task with file locations]
2. [Next task...]

## Specific Issues Found:
- [file:line] Issue description

## Commit Instructions:
```bash
git add [files]
git commit -m "[Component] Description

- Changes made
- Files affected

Completeness: X/100"
```

## Next Instructions for Agent 1:
[Detailed, specific instructions for the next implementation cycle]

DO NOT accept incomplete work. Push for full implementation.
"""
