"""Pytest fixtures for CCConfigManager backend tests.

All filesystem operations are isolated to tmp_path. External dependencies
(Anthropic API, subprocess, network) are mocked at fixture level.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Ensure src/ is on sys.path so ``from ccconfigmanager import ...`` works
# ---------------------------------------------------------------------------
_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ---------------------------------------------------------------------------
# Low-level helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_cache():
    """Clear ccconfigmanager modules before each test so singleton re-creation
    picks up the monkeypatched HOME/USERPROFILE."""
    yield
    # Teardown: nothing special needed


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    """Redirect $HOME / $USERPROFILE to an isolated temporary directory.

    Creates the minimal ``~/.claude/`` skeleton so that registry imports
    (Scanner, SourceDetector, Mover) operate on an empty, safe filesystem.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    # --- Create the directories that scanner.py expects ---
    dot_claude = tmp_path / ".claude"
    dot_claude.mkdir(exist_ok=True)

    for sub in (
        "CCConfigManager",
        "skills",
        "skills-archive",
        "agents",
        "agents-archive",
        "commands",
        "commands-archive",
        "rules",
        "rules-archive",
        "workflows",
        "hooks",
        "mcp-configs",
    ):
        (dot_claude / sub).mkdir(parents=True, exist_ok=True)

    # Pre-seed projects.json and packs.json so that the data-layer helpers
    # do not raise.
    (dot_claude / "CCConfigManager" / "projects.json").write_text(
        '{"projects": {}}', encoding="utf-8"
    )
    (dot_claude / "CCConfigManager" / "packs.json").write_text(
        '{"packs": {}}', encoding="utf-8"
    )

    (dot_claude / "mcp-configs" / "mcp-servers.json").write_text(
        '{"mcpServers": {}}', encoding="utf-8"
    )

    return tmp_path


@pytest.fixture
def fresh_app(tmp_home):
    """Return a fresh FastAPI ``app`` instance whose registry singletons
    point at the isolated ``tmp_home/.claude/`` directory.

    Because ``registry.py`` creates Scanner / SourceDetector / Mover at
    module-import time, we must delete the cached modules *after* the
    environment variables have been set by ``tmp_home``.
    """
    # Wipe any previously imported ccconfigmanager modules so they
    # re-create their singletons with the patched HOME.
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("ccconfigmanager"):
            del sys.modules[mod_name]

    from ccconfigmanager.app import app

    return app


@pytest.fixture
def client(fresh_app):
    """FastAPI TestClient backed by the isolated app."""
    from fastapi.testclient import TestClient

    return TestClient(fresh_app)


# ---------------------------------------------------------------------------
# Mocked external-dependency fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_subprocess_run():
    """Prevent real subprocess calls; return a canned CompletedProcess."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(
            stdout="hello world",
            stderr="",
            returncode=0,
        )
        yield mock


@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Mock ``anthropic.Anthropic`` so that gate tests never hit the real API."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    # Clear the module-level client cache so each test gets a fresh mock
    import ccconfigmanager.executor.gate as gate_module
    gate_module._client = None
    gate_module._client_key = ""
    with patch("ccconfigmanager.executor.gate.Anthropic") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance

        # Default response: "YES" -> gate passes
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="YES")]
        mock_instance.messages.create.return_value = mock_message

        yield mock_cls


@pytest.fixture
def mock_urlopen():
    """Prevent real network calls from WebFetch / WebSearch tools."""
    with patch("urllib.request.urlopen") as mock:
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html><body>mock response</body></html>"
        mock_response.__enter__.return_value = mock_response
        mock.return_value = mock_response
        yield mock


# ---------------------------------------------------------------------------
# Sandbox fixture (used by tool tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox(tmp_path):
    """A ``Sandbox`` instance bound to an isolated project root."""
    from ccconfigmanager.executor.sandbox import Sandbox

    return Sandbox(project_path=str(tmp_path))


# ---------------------------------------------------------------------------
# Scanner / SourceDetector fixture helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_scanner():
    """A fully-mocked Scanner that returns controlled item data.

    Callers should configure ``mock.scan_all.return_value``.
    """
    with patch("ccconfigmanager.registry.scanner") as mock:
        yield mock


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_SKILL_ITEM = {
    "type": "skill",
    "name": "test-skill",
    "source": "standalone",
    "status": "active",
    "path": "/tmp/.claude/skills/test-skill",
    "paths": ["/tmp/.claude/skills/test-skill"],
    "description": "A test skill",
    "content_preview": "Test content preview",
}

SAMPLE_RULE_ITEM = {
    "type": "rule",
    "name": "test-rule",
    "source": "standalone",
    "status": "active",
    "path": "/tmp/.claude/rules/test-rule.md",
    "paths": ["/tmp/.claude/rules/test-rule.md"],
    "description": "A test rule",
    "content_preview": "Test rule content",
}
