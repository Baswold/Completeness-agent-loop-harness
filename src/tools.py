import os
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import json


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None


class ToolRegistry:
    def __init__(self, workspace: Path, agent_name: str = "agent1"):
        self.workspace = workspace
        self.agent_name = agent_name  # "agent1" or "agent2"
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        self.register("bash", self._bash, {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command in the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds (default 120)",
                            "default": 120
                        }
                    },
                    "required": ["command"]
                }
            }
        })
        
        self.register("file_read", self._file_read, {
            "type": "function",
            "function": {
                "name": "file_read",
                "description": "Read the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file (relative to workspace)"
                        }
                    },
                    "required": ["path"]
                }
            }
        })
        
        self.register("file_write", self._file_write, {
            "type": "function",
            "function": {
                "name": "file_write",
                "description": "Write content to a file (creates directories if needed)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file (relative to workspace)"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        })
        
        self.register("file_delete", self._file_delete, {
            "type": "function",
            "function": {
                "name": "file_delete",
                "description": "Delete a file or directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to delete (relative to workspace)"
                        }
                    },
                    "required": ["path"]
                }
            }
        })
        
        self.register("list_directory", self._list_directory, {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List contents of a directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to directory (relative to workspace, default is root)",
                            "default": "."
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "List recursively",
                            "default": False
                        }
                    }
                }
            }
        })
        
        self.register("search_files", self._search_files, {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search for files matching a pattern",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern to match (e.g., '*.py', '**/*.js')"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        })
        
        self.register("search_content", self._search_content, {
            "type": "function",
            "function": {
                "name": "search_content",
                "description": "Search for text content in files",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Text or regex pattern to search for"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Glob pattern for files to search (default: all files)",
                            "default": "**/*"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        })
        
        self.register("git_status", self._git_status, {
            "type": "function",
            "function": {
                "name": "git_status",
                "description": "Get git status of the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        })
        
        self.register("git_add", self._git_add, {
            "type": "function",
            "function": {
                "name": "git_add",
                "description": "Stage files for commit",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of paths to stage (use ['.'] for all)"
                        }
                    },
                    "required": ["paths"]
                }
            }
        })
        
        self.register("git_commit", self._git_commit, {
            "type": "function",
            "function": {
                "name": "git_commit",
                "description": "Commit staged changes",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Commit message"
                        }
                    },
                    "required": ["message"]
                }
            }
        })
        
        self.register("git_log", self._git_log, {
            "type": "function",
            "function": {
                "name": "git_log",
                "description": "Get recent git commit history",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of commits to show",
                            "default": 10
                        }
                    }
                }
            }
        })
        
        self.register("run_tests", self._run_tests, {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "Run tests using pytest, jest, or other test frameworks",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Test command (e.g., 'pytest', 'npm test')",
                            "default": "pytest"
                        },
                        "path": {
                            "type": "string",
                            "description": "Path to tests",
                            "default": "."
                        }
                    }
                }
            }
        })

        self.register("memory_read", self._memory_read, {
            "type": "function",
            "function": {
                "name": "memory_read",
                "description": "Read YOUR agent-specific memory file to understand project context, lessons learned, and important information from your previous iterations. This is YOUR personal memory - other agents cannot see it.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        })

        self.register("memory_write", self._memory_write, {
            "type": "function",
            "function": {
                "name": "memory_write",
                "description": "Save important information to YOUR agent-specific memory file. Use this to document: project architecture, key decisions, lessons learned, common errors and solutions, important file locations, testing strategies, and any knowledge that would help YOUR future iterations. You SHOULD use this before finishing your work to help yourself in the next iteration.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "section": {
                            "type": "string",
                            "description": "Section header for the memory entry (e.g., 'Architecture', 'Lessons Learned', 'Common Issues')"
                        },
                        "content": {
                            "type": "string",
                            "description": "The information to save. Be specific and actionable."
                        },
                        "append": {
                            "type": "boolean",
                            "description": "If true, append to existing section. If false, replace section content.",
                            "default": True
                        }
                    },
                    "required": ["section", "content"]
                }
            }
        })
    
    def register(self, name: str, func: Callable, schema: Dict):
        self._tools[name] = func
        self._schemas[name] = schema
    
    def get_schemas(self) -> List[Dict]:
        return list(self._schemas.values())
    
    def execute(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(False, "", f"Unknown tool: {name}")
        
        try:
            return self._tools[name](**arguments)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate that a path stays within the workspace.
        Prevents directory traversal attacks and symlink escapes.
        """
        workspace_abs = self.workspace.resolve()

        # Resolve the target path
        if path.startswith("/"):
            # Absolute paths are not allowed
            raise PermissionError(
                f"Access denied: Absolute paths are not allowed. "
                f"Use relative paths only. Path: {path}"
            )

        # Construct the full path
        target = workspace_abs / path
        target_abs = target.resolve()

        # Check if resolved path is within workspace
        try:
            target_abs.relative_to(workspace_abs)
        except ValueError:
            raise PermissionError(
                f"Access denied: {path} is outside workspace. "
                f"All operations must stay within {workspace_abs}"
            )

        return target_abs

    def _resolve_path(self, path: str) -> Path:
        """Alias for _validate_path for backwards compatibility."""
        return self._validate_path(path)
    
    def _bash(self, command: str, timeout: int = 120) -> ToolResult:
        try:
            # Prevent directory escape attempts
            forbidden_patterns = [
                r"cd\s+/",  # cd to absolute paths
                r"cd\s+\.\.",  # cd to parent directory
                r"/etc/",  # access to system directories
                r"/var/",
                r"/usr/",
                r"/bin/",
                r"/sbin/",
                r"/root/",
                r"/home/[^/]*$",  # home directory outside workspace
            ]

            import re
            for pattern in forbidden_patterns:
                if re.search(pattern, command):
                    return ToolResult(
                        False,
                        "",
                        f"Command blocked: Detected attempt to access files outside workspace. "
                        f"All commands must operate within the workspace directory."
                    )

            result = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _file_read(self, path: str) -> ToolResult:
        try:
            file_path = self._resolve_path(path)
            if not file_path.exists():
                return ToolResult(False, "", f"File not found: {path}")
            content = file_path.read_text()
            return ToolResult(True, content)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _file_write(self, path: str, content: str) -> ToolResult:
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            return ToolResult(True, f"Written to {path}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _file_delete(self, path: str) -> ToolResult:
        try:
            file_path = self._resolve_path(path)
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            return ToolResult(True, f"Deleted {path}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _list_directory(self, path: str = ".", recursive: bool = False) -> ToolResult:
        try:
            dir_path = self._resolve_path(path)
            if not dir_path.is_dir():
                return ToolResult(False, "", f"Not a directory: {path}")
            
            if recursive:
                files = []
                for p in dir_path.rglob("*"):
                    rel = p.relative_to(self.workspace)
                    if p.is_file():
                        files.append(str(rel))
                output = "\n".join(sorted(files))
            else:
                entries = []
                for p in sorted(dir_path.iterdir()):
                    prefix = "d " if p.is_dir() else "f "
                    entries.append(prefix + p.name)
                output = "\n".join(entries)
            
            return ToolResult(True, output)
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _search_files(self, pattern: str) -> ToolResult:
        try:
            matches = list(self.workspace.glob(pattern))
            files = [str(p.relative_to(self.workspace)) for p in matches if p.is_file()]
            return ToolResult(True, "\n".join(sorted(files)))
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _search_content(self, pattern: str, file_pattern: str = "**/*") -> ToolResult:
        try:
            result = subprocess.run(
                ["grep", "-rn", pattern, "."],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=60
            )
            return ToolResult(True, result.stdout or "No matches found")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _git_status(self) -> ToolResult:
        return self._bash("git status")
    
    def _git_add(self, paths: List[str]) -> ToolResult:
        paths_str = " ".join(f'"{p}"' for p in paths)
        return self._bash(f"git add {paths_str}")
    
    def _git_commit(self, message: str) -> ToolResult:
        escaped_msg = message.replace('"', '\\"')
        return self._bash(f'git commit -m "{escaped_msg}"')
    
    def _git_log(self, count: int = 10) -> ToolResult:
        return self._bash(f"git log --oneline -n {count}")
    
    def _run_tests(self, command: str = "pytest", path: str = ".") -> ToolResult:
        return self._bash(f"{command} {path}")

    def _memory_read(self) -> ToolResult:
        """Read the agent-specific memory file."""
        try:
            # Each agent gets their own memory file to maintain isolation
            memory_file = self.workspace / f"{self.agent_name.upper()}_MEMORY.md"

            if not memory_file.exists():
                # Create initial memory file with agent-specific template
                if self.agent_name == "agent1":
                    initial_content = """# Agent 1 Implementation Memory

This is YOUR personal memory file. Agent 2 cannot see this.
Use it to remember what you've learned across iterations.

## Architecture
(Project structure and key design decisions you've made)

## Implementation Strategies
(Approaches that worked well for implementing features)

## Common Errors & Solutions
(Bugs you encountered and how you fixed them)

## Testing Commands
(How to run tests, what test frameworks are being used)

## Important Files
(Key files you created/modified and their purposes)

## Dependencies & Setup
(Packages installed, configuration needed)

## Next Steps
(What you should prioritize in your next iteration)
"""
                else:  # agent2
                    initial_content = """# Agent 2 Review Memory

This is YOUR personal memory file. Agent 1 cannot see this.
Use it to remember patterns and issues you've observed.

## Incomplete Patterns
(Common ways Agent 1 claims completeness but isn't complete)

## Testing Gaps
(Types of tests Agent 1 frequently forgets)

## Code Quality Issues
(Recurring code quality problems to watch for)

## Specification Mismatches
(Parts of the spec Agent 1 tends to miss or misinterpret)

## Review Strategies
(Effective approaches for catching incompleteness)

## Project Progress
(Objective assessment of what's actually working)

## Priority Issues
(Most critical problems that need fixing next)
"""
                memory_file.write_text(initial_content)
                return ToolResult(True, initial_content)

            content = memory_file.read_text()
            return ToolResult(True, content)
        except Exception as e:
            return ToolResult(False, "", str(e))

    def _memory_write(self, section: str, content: str, append: bool = True) -> ToolResult:
        """Write to the agent-specific memory file."""
        try:
            # Each agent writes to their own memory file
            memory_file = self.workspace / f"{self.agent_name.upper()}_MEMORY.md"

            # Read existing content or create new
            if memory_file.exists():
                existing_content = memory_file.read_text()
            else:
                # Create with agent-specific header
                header = "Agent 1 Implementation Memory" if self.agent_name == "agent1" else "Agent 2 Review Memory"
                existing_content = f"# {header}\n\n"

            # Find or create section
            section_header = f"## {section}"
            lines = existing_content.split('\n')

            # Find section start and end
            section_start = -1
            section_end = -1
            for i, line in enumerate(lines):
                if line.strip() == section_header:
                    section_start = i
                elif section_start >= 0 and line.strip().startswith("## "):
                    section_end = i
                    break

            if section_start == -1:
                # Section doesn't exist, add at end
                if not existing_content.endswith('\n\n'):
                    existing_content += '\n\n'
                new_content = existing_content + f"{section_header}\n{content}\n"
            else:
                # Section exists
                if section_end == -1:
                    section_end = len(lines)

                if append:
                    # Append to existing section
                    lines.insert(section_end, content)
                else:
                    # Replace section content
                    lines = lines[:section_start+1] + [content] + lines[section_end:]

                new_content = '\n'.join(lines)

            memory_file.write_text(new_content)
            return ToolResult(True, f"Memory updated in section '{section}' ({self.agent_name})")
        except Exception as e:
            return ToolResult(False, "", str(e))
