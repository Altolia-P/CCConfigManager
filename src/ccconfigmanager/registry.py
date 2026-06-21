"""Shared singletons — Scanner, SourceDetector, Mover. Imported by app and all route modules."""

import os
import sys

from .scanner import Scanner
from .source_detector import SourceDetector
from .mover import Mover

CLAUDE_DIR = os.path.expanduser("~/.claude")


def get_static_dir() -> str:
    """Return the static files directory, handling PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        return os.path.join(sys._MEIPASS, "ccconfigmanager", "static")
    # Running from source — this file is at src/ccconfigmanager/registry.py
    return os.path.join(os.path.dirname(__file__), "static")

detector = SourceDetector(CLAUDE_DIR)
scanner = Scanner(CLAUDE_DIR, detector)
mover = Mover(CLAUDE_DIR)

# Plural → singular mapping for API type keys
TYPE_MAP = {
    "skills": "skill", "agents": "agent", "commands": "command",
    "rules": "rule", "mcps": "mcp", "tools": "tool",
    "workflows": "workflow", "hooks": "hook",
}

ALL_TYPES = ["skills", "agents", "commands", "rules", "mcps", "tools", "workflows", "hooks"]
