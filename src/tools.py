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
    def __init__(self, workspace: Path):
        self.workspace = workspace
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
    
    def _resolve_path(self, path: str) -> Path:
        resolved = self.workspace / path
        resolved = resolved.resolve()
        if not str(resolved).startswith(str(self.workspace.resolve())):
            raise ValueError(f"Path escapes workspace: {path}")
        return resolved
    
    def _bash(self, command: str, timeout: int = 120) -> ToolResult:
        try:
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
