import subprocess
from pathlib import Path
from typing import List, Optional, Set


class ContextBuilder:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.ignore_patterns = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".env", ".idea", ".vscode", "*.pyc", "*.pyo", ".DS_Store",
            "*.egg-info", "dist", "build", ".pytest_cache", ".mypy_cache"
        }
    
    def build_file_tree(self, max_depth: int = 10) -> str:
        lines = []
        self._walk_tree(self.workspace, lines, "", max_depth)
        return "\n".join(lines)
    
    def _walk_tree(self, path: Path, lines: List[str], prefix: str, depth: int):
        if depth <= 0:
            return
        
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        
        filtered = [e for e in entries if not self._should_ignore(e)]
        
        for i, entry in enumerate(filtered):
            is_last = i == len(filtered) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk_tree(entry, lines, prefix + extension, depth - 1)
    
    def _should_ignore(self, path: Path) -> bool:
        name = path.name
        for pattern in self.ignore_patterns:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False
    
    def read_all_source_files(self, extensions: Optional[Set[str]] = None) -> str:
        if extensions is None:
            extensions = {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
                ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
                ".scala", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".json",
                ".toml", ".ini", ".cfg", ".md", ".txt", ".html", ".css",
                ".scss", ".less", ".sql", ".graphql", ".proto"
            }
        
        contents = []
        for file_path in self.workspace.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                if self._should_ignore(file_path):
                    continue
                if any(self._should_ignore(p) for p in file_path.parents):
                    continue
                
                try:
                    rel_path = file_path.relative_to(self.workspace)
                    content = file_path.read_text(errors="replace")
                    contents.append(f"### {rel_path}\n```\n{content}\n```\n")
                except Exception:
                    continue
        
        return "\n".join(contents)
    
    def get_git_log(self, count: int = 10) -> str:
        try:
            result = subprocess.run(
                ["git", "log", f"-n{count}", "--pretty=format:%h %s (%cr)"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout if result.returncode == 0 else "No git history"
        except Exception:
            return "Git not available"
    
    def get_last_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=format:%h %s\n\n%b"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""
    
    def build_agent1_context(self, focus_files: Optional[List[str]] = None) -> str:
        tree = self.build_file_tree()
        
        if focus_files:
            file_contents = []
            for file_path in focus_files:
                full_path = self.workspace / file_path
                if full_path.exists() and full_path.is_file():
                    try:
                        content = full_path.read_text(errors="replace")
                        file_contents.append(f"### {file_path}\n```\n{content}\n```\n")
                    except Exception:
                        pass
            files_str = "\n".join(file_contents)
        else:
            files_str = self.read_all_source_files()
        
        return f"""### File Tree
```
{tree}
```

### Source Files
{files_str}
"""
    
    def build_agent2_context(self) -> str:
        tree = self.build_file_tree()
        files_str = self.read_all_source_files()
        git_log = self.get_git_log()
        
        return f"""### File Tree
```
{tree}
```

### Source Files
{files_str}

### Git Log
```
{git_log}
```
"""
    
    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4
