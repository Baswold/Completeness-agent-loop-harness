import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from .llm import LLMBackend, LLMResponse, TokenUsage
from .tools import ToolRegistry, ToolResult


@dataclass
class AgentResponse:
    content: str
    tool_calls_made: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    iterations: int = 0


class Agent1:
    def __init__(
        self,
        llm: LLMBackend,
        tools: ToolRegistry,
        system_prompt: str,
        max_iterations: int = 20
    ):
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
    
    def run(
        self,
        instructions: str,
        codebase_context: str,
        last_commit: Optional[str] = None,
        task_summary: Optional[str] = None
    ) -> AgentResponse:
        messages = [{"role": "system", "content": self.system_prompt}]

        # Read Agent 1's own memory at the start (just like Agent 2 does)
        memory_content = ""
        memory_result = self.tools.execute('memory_read', {})
        if memory_result.success:
            memory_content = f"""## YOUR MEMORY (Agent 1)
{memory_result.output}

"""

        user_content = memory_content + f"""## CODEBASE SNAPSHOT
{codebase_context}

"""
        if last_commit:
            user_content += f"""## LAST COMMIT
{last_commit}

"""
        if task_summary:
            user_content += f"""## TASK CONTEXT
{task_summary}

"""
        user_content += f"""## INSTRUCTIONS
{instructions}

Execute these instructions now. Use the available tools to implement the required changes.
"""
        messages.append({"role": "user", "content": user_content})
        
        total_usage = TokenUsage()
        all_tool_calls = []
        all_tool_results = []
        final_content = ""
        iteration = 0
        
        tool_schemas = self.tools.get_schemas() if self.llm.supports_tools() else None
        
        for iteration in range(self.max_iterations):
            response = self.llm.generate(
                messages=messages,
                tools=tool_schemas,
                max_tokens=4096
            )
            
            total_usage = total_usage + response.usage
            
            if not response.tool_calls:
                final_content = response.content
                break
            
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls
            })
            
            for tool_call in response.tool_calls:
                func = tool_call.get("function", {})
                tool_name = func.get("name", "")
                try:
                    arguments = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}
                
                result = self.tools.execute(tool_name, arguments)
                all_tool_calls.append({"name": tool_name, "arguments": arguments})
                all_tool_results.append(result)
                
                tool_id = tool_call.get("id", f"call_{iteration}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result.output if result.success else f"Error: {result.error}"
                })
            
            if response.finish_reason == "stop":
                final_content = response.content
                break
        
        return AgentResponse(
            content=final_content,
            tool_calls_made=all_tool_calls,
            tool_results=all_tool_results,
            usage=total_usage,
            iterations=iteration + 1
        )


class Agent2:
    def __init__(self, llm: LLMBackend, system_prompt: str, tools: Optional[ToolRegistry] = None):
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools = tools  # For memory access only

    def review(
        self,
        original_spec: str,
        codebase_context: str,
        git_log: str
    ) -> "ReviewResult":
        messages = [{"role": "system", "content": self.system_prompt}]

        # Read Agent 2's own memory if tools are available
        memory_content = ""
        if self.tools:
            memory_result = self.tools.execute('memory_read', {})
            if memory_result.success:
                memory_content = f"""## YOUR MEMORY (Agent 2)
{memory_result.output}

"""

        user_content = memory_content + f"""## ORIGINAL SPECIFICATION
{original_spec}

## CURRENT CODEBASE
{codebase_context}

## GIT LOG (Recent Commits)
{git_log}

Review the codebase against the specification. Rate completeness and provide specific next instructions.
Do NOT trust claims in commit messages - verify everything in the actual code.

IMPORTANT: Before finishing your review, use memory_write() to save any important observations about:
- Patterns of incompleteness you've noticed
- Testing gaps that keep recurring
- Code quality issues to watch for
- Parts of the spec that keep being missed
"""
        messages.append({"role": "user", "content": user_content})

        # Get tool schemas for memory operations only
        tool_schemas = None
        if self.tools and self.llm.supports_tools():
            # Filter to only memory tools
            all_schemas = self.tools.get_schemas()
            tool_schemas = [s for s in all_schemas if s['function']['name'] in ['memory_read', 'memory_write']]

        response = self.llm.generate(
            messages=messages,
            tools=tool_schemas,
            max_tokens=4096
        )

        # If Agent2 made tool calls (memory writes), execute them
        if response.tool_calls and self.tools:
            for tool_call in response.tool_calls:
                if tool_call.get('function', {}).get('name') in ['memory_write']:
                    try:
                        args = json.loads(tool_call['function']['arguments'])
                        self.tools.execute('memory_write', args)
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        # Silently skip malformed tool calls - Agent2's review is more important
                        pass

        return ReviewResult.parse(response.content, response.usage)


@dataclass
class ReviewResult:
    raw_content: str
    completeness_score: int
    completed_items: List[str]
    remaining_work: List[str]
    issues_found: List[str]
    commit_instructions: str
    next_instructions: str
    usage: TokenUsage
    is_complete: bool = False
    
    @classmethod
    def parse(cls, content: str, usage: TokenUsage) -> "ReviewResult":
        score = 0
        completed = []
        remaining = []
        issues = []
        commit_instr = ""
        next_instr = ""
        
        lines = content.split("\n")
        current_section = None
        section_content = []
        
        for line in lines:
            line_lower = line.lower().strip()

            # More robust score parsing - handle multiple formats
            # Check for "completeness" + any number in the same line or nearby
            if "completeness" in line_lower or "complete" in line_lower and current_section != "completed":
                import re
                # Try to find patterns like "X/100", "X%", ": X", or just "X"
                match = re.search(r"(\d+)\s*/\s*100", line) or \
                        re.search(r"(\d+)\s*%", line) or \
                        re.search(r":\s*(\d+)", line) or \
                        re.search(r"\b(\d+)\b", line)  # Any standalone number
                if match:
                    potential_score = int(match.group(1))
                    # Only accept scores 0-100
                    if 0 <= potential_score <= 100:
                        score = potential_score
                        current_section = "score"
                        continue
            elif "what was just completed" in line_lower or "completed:" in line_lower:
                current_section = "completed"
                continue
            elif "remaining work" in line_lower:
                current_section = "remaining"
                continue
            elif "issues found" in line_lower or "specific issues" in line_lower:
                current_section = "issues"
                continue
            elif "commit instructions" in line_lower:
                current_section = "commit"
                section_content = []
                continue
            elif "next instructions" in line_lower or "instructions for agent" in line_lower:
                if current_section == "commit":
                    commit_instr = "\n".join(section_content)
                current_section = "next"
                section_content = []
                continue
            
            if current_section == "completed" and line.strip().startswith("-"):
                completed.append(line.strip()[1:].strip())
            elif current_section == "remaining" and (line.strip().startswith("-") or line.strip()[:2].replace(".", "").isdigit()):
                remaining.append(line.strip().lstrip("-0123456789. "))
            elif current_section == "issues" and line.strip().startswith("-"):
                issues.append(line.strip()[1:].strip())
            elif current_section in ("commit", "next"):
                section_content.append(line)
        
        if current_section == "commit":
            commit_instr = "\n".join(section_content)
        elif current_section == "next":
            next_instr = "\n".join(section_content)
        
        if not next_instr and section_content:
            next_instr = "\n".join(section_content)
        
        is_complete = score >= 95 and not remaining
        
        return cls(
            raw_content=content,
            completeness_score=score,
            completed_items=completed,
            remaining_work=remaining,
            issues_found=issues,
            commit_instructions=commit_instr,
            next_instructions=next_instr or content,
            usage=usage,
            is_complete=is_complete
        )
