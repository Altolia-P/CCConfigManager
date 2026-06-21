"""Sandbox constraints for workflow execution."""

import os
import re
from pathlib import Path


class Sandbox:
    def __init__(self, project_path: str, blocked_patterns: list[str] | None = None):
        self.project_root = Path(project_path).resolve()
        self.blocked_patterns = blocked_patterns or [
            r"\.env$", r"\.git/", r"node_modules/",
            r"__pycache__/", r"\.venv/", r"\.credentials"
        ]

    def is_allowed_path(self, path: str) -> bool:
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            return False
        return True

    def is_blocked(self, path: str) -> bool:
        for pattern in self.blocked_patterns:
            if re.search(pattern, str(path)):
                return True
        return False

    def resolve_safe(self, path: str) -> Path:
        if not path:
            raise ValueError("Empty path")
        p = Path(path)
        if p.is_absolute():
            resolved = p.resolve()
        else:
            resolved = (self.project_root / p).resolve()
        if not self.is_allowed_path(str(resolved)):
            raise PermissionError(f"路径不在项目范围内: {resolved}")
        return resolved
