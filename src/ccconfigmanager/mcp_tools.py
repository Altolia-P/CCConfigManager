"""MCP tool discovery — connect to MCP servers, list their tools, cache results."""
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

_SEP = "\r\n" if os.name == "nt" else "\n"


def cache_path(claude_dir: str) -> Path:
    return Path(claude_dir) / "mcp-configs" / ".tools-cache.json"


def load_cache(claude_dir: str) -> dict[str, list]:
    cp = cache_path(claude_dir)
    if cp.is_file():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def discover_and_cache(claude_dir: str, force: bool = False) -> dict[str, list]:
    existing = {} if force else load_cache(claude_dir)
    mcp_file = Path(claude_dir) / "mcp-configs" / "mcp-servers.json"
    if not mcp_file.is_file():
        return {}

    try:
        config = json.loads(mcp_file.read_text(encoding="utf-8"))
    except Exception:
        return existing

    servers = config.get("mcpServers", {})
    discovered_any = False

    for name, cfg in servers.items():
        if name in existing and not force:
            continue
        command = cfg.get("command", "")
        if not command or cfg.get("type") == "http":
            if force and name not in existing:
                existing[name] = []
            continue
        tools = _discover_one(name, cfg)
        if tools is not None:
            existing[name] = tools
            discovered_any = True
        elif name not in existing:
            existing[name] = []

    if discovered_any or force:
        cp = cache_path(claude_dir)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return existing


def _resolve_command(command: str) -> str:
    """Find the full path to an executable, especially on Windows."""
    exe = shutil.which(command)
    if exe:
        return exe
    # On Windows, also try .cmd extension
    if os.name == "nt":
        exe = shutil.which(command + ".cmd")
        if exe:
            return exe
    return command


def _discover_one(name: str, cfg: dict) -> list | None:
    command = cfg.get("command", "")
    args = list(cfg.get("args", []))
    env_cfg = cfg.get("env", {})

    resolved = _resolve_command(command)

    env_full = os.environ.copy()
    for k, v in env_cfg.items():
        if v and "YOUR_" not in v and "YOUR_" not in k:
            env_full[k] = v

    try:
        proc = subprocess.Popen(
            [resolved] + args,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env_full,
            text=True, bufsize=1,
        )
    except Exception:
        return None

    try:
        _write(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "CCConfigManager", "version": "1.0"}}})
        init_resp = _read(proc, timeout=12)
        if init_resp is None or "result" not in init_resp:
            return None

        _write(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _write(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_resp = _read(proc, timeout=10)

        if tools_resp and "result" in tools_resp:
            raw_tools = tools_resp["result"].get("tools", [])
            return [{"name": t.get("name", ""), "description": t.get("description", ""),
                     "server": name} for t in raw_tools if isinstance(t, dict)]
    except Exception:
        pass
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    return None


def _write(proc, msg: dict) -> None:
    proc.stdin.write(json.dumps(msg) + _SEP)
    proc.stdin.flush()


def _read(proc, timeout: float = 10) -> dict | None:
    result: list = [None]

    def reader():
        try:
            line = proc.stdout.readline()
            if line:
                result[0] = json.loads(line)
        except Exception:
            pass

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(timeout)
    return result[0]
