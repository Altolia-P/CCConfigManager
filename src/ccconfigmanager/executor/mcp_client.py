"""Generic MCP JSON-RPC client.

Supports any MCP server (stdio type) listed in ~/.claude/mcp-configs/mcp-servers.json.
Newly downloaded MCP servers work automatically — no hardcoded server names or tools.

Architecture: McpClient (single server process) → McpManager (multi-server lifecycle).
"""

import json
import os
import shutil
import subprocess
import threading
import urllib.request
import urllib.error
from pathlib import Path

_SEP = "\r\n" if os.name == "nt" else "\n"
MCP_CONFIG_PATH = Path.home() / ".claude" / "mcp-configs" / "mcp-servers.json"
HTTP_TIMEOUT = 30


def _resolve_exe(command: str) -> str:
    exe = shutil.which(command)
    if exe:
        return exe
    if os.name == "nt":
        exe = shutil.which(command + ".cmd")
        if exe:
            return exe
    return command


class McpClient:
    """JSON-RPC connection to a single MCP server subprocess."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self.proc: subprocess.Popen | None = None
        self._next_id = 100
        self._lock = threading.Lock()
        self._tool_cache: list[dict] | None = None

    # ---- lifecycle ----

    def start(self) -> bool:
        command = self.config.get("command", "")
        if not command:
            return False
        resolved = _resolve_exe(command)
        args = list(self.config.get("args", []))
        env_full = os.environ.copy()
        for k, v in self.config.get("env", {}).items():
            if v:
                env_full[k] = v
        try:
            self.proc = subprocess.Popen(
                [resolved] + args,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=env_full,
                text=True, bufsize=1,
            )
        except Exception:
            return False

        init = self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "CCConfigManager", "version": "1.0"},
        })
        if init is None or "result" not in init:
            self.stop()
            return False
        self._notify("notifications/initialized")
        return True

    def stop(self) -> None:
        if not self.proc:
            return
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=4)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None
        self._tool_cache = None

    # ---- MCP protocol methods ----

    def list_tools(self) -> list[dict]:
        if self._tool_cache is not None:
            return self._tool_cache
        resp = self._call("tools/list", {})
        if resp and "result" in resp:
            self._tool_cache = resp["result"].get("tools", [])
            return self._tool_cache
        return []

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        resp = self._call("tools/call", {"name": tool_name, "arguments": arguments})
        if resp is None:
            return f"MCP server '{self.name}' 无响应"
        if "error" in resp:
            err = resp["error"]
            return f"MCP 错误 [{self.name}]: {err.get('message', str(err))}"
        content = resp.get("result", {}).get("content", [])
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    texts.append(item.get("text", json.dumps(item, ensure_ascii=False)))
                else:
                    texts.append(str(item))
            return "\n".join(texts) if texts else "(MCP 工具无文本输出)"
        return str(content)

    # ---- JSON-RPC plumbing ----

    def _next_req_id(self) -> int:
        with self._lock:
            self._next_id += 1
            return self._next_id

    def _call(self, method: str, params: dict) -> dict | None:
        """Send a JSON-RPC request and read the response."""
        req_id = self._next_req_id()
        return self._rpc({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})

    def _notify(self, method: str) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        self._write({"jsonrpc": "2.0", "method": method})

    def _write(self, msg: dict) -> None:
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.write(json.dumps(msg) + _SEP)
                self.proc.stdin.flush()
        except Exception:
            pass

    def _rpc(self, msg: dict) -> dict | None:
        """Write request and read single-line JSON response with timeout."""
        if not self.proc or not self.proc.stdout:
            return None
        result: list[dict | None] = [None]
        ready = threading.Event()

        def reader():
            try:
                self._write(msg)
                line = self.proc.stdout.readline()
                if line:
                    result[0] = json.loads(line)
            except Exception:
                pass
            finally:
                ready.set()

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        ready.wait(timeout=15)
        return result[0]


class McpHttpClient:
    """JSON-RPC client for HTTP-type MCP servers.

    Communicates via HTTP POST (JSON-RPC over HTTP). Supports standard MCP
    servers that expose an HTTP endpoint instead of stdio.
    """

    def __init__(self, name: str, config: dict):
        self.name = name
        self.url = config.get("url", "")
        self._next_id = 100
        self._lock = threading.Lock()
        self._tool_cache: list[dict] | None = None
        self._started = False

    def start(self) -> bool:
        if not self.url:
            return False
        init = self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "CCConfigManager", "version": "1.0"},
        })
        if init is None or "result" not in init:
            return False
        self._notify("notifications/initialized")
        self._started = True
        return True

    def stop(self) -> None:
        self._started = False
        self._tool_cache = None

    def list_tools(self) -> list[dict]:
        if self._tool_cache is not None:
            return self._tool_cache
        resp = self._call("tools/list", {})
        if resp and "result" in resp:
            self._tool_cache = resp["result"].get("tools", [])
            return self._tool_cache
        return []

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        resp = self._call("tools/call", {"name": tool_name, "arguments": arguments})
        if resp is None:
            return f"MCP HTTP server '{self.name}' 无响应"
        if "error" in resp:
            err = resp["error"]
            return f"MCP 错误 [{self.name}]: {err.get('message', str(err))}"
        content = resp.get("result", {}).get("content", [])
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    texts.append(item.get("text", json.dumps(item, ensure_ascii=False)))
                else:
                    texts.append(str(item))
            return "\n".join(texts) if texts else "(MCP 工具无文本输出)"
        return str(content)

    def _next_req_id(self) -> int:
        with self._lock:
            self._next_id += 1
            return self._next_id

    def _call(self, method: str, params: dict) -> dict | None:
        req_id = self._next_req_id()
        req_body = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}, ensure_ascii=False)
        try:
            req = urllib.request.Request(
                self.url,
                data=req_body.encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def _notify(self, method: str) -> None:
        try:
            req_body = json.dumps({"jsonrpc": "2.0", "method": method}, ensure_ascii=False)
            req = urllib.request.Request(
                self.url,
                data=req_body.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)
        except Exception:
            pass


class McpManager:
    """Manages lifecycle of multiple MCP server connections.

    Usage:
        mgr = McpManager()
        # Get Anthropic-compatible tool definitions for selected servers
        mcp_tool_defs, tool_server_map = mgr.get_tool_defs(["github", "memory"])
        # ... pass mcp_tool_defs to Claude API alongside built-in tools ...
        # On tool_use, check tool_server_map and dispatch:
        result = mgr.execute("github", tool_name, tool_input)
        # ... when done ...
        mgr.shutdown()
    """

    def __init__(self):
        self._clients: dict[str, McpClient] = {}
        self._tool_map: dict[str, str] = {}  # tool_name → server_name
        self._configs: dict = {}

    def load_configs(self) -> dict:
        if MCP_CONFIG_PATH.is_file():
            try:
                self._configs = json.loads(
                    MCP_CONFIG_PATH.read_text(encoding="utf-8")
                ).get("mcpServers", {})
            except Exception:
                self._configs = {}
        return self._configs

    def get_tool_defs(self, names: list[str]) -> tuple[list[dict], dict[str, str]]:
        """Return (Anthropic tool definitions, tool_name→server_name mapping).

        Only starts servers that aren't already running. Unrecognized names are
        silently skipped (the server may not be in mcp-servers.json or may have
        failed to start).
        """
        if not self._configs:
            self.load_configs()

        defs: list[dict] = []
        for name in names:
            client = self._ensure(name)
            if not client:
                continue
            for tool in client.list_tools():
                schema = tool.get("inputSchema") or {
                    "type": "object",
                    "properties": {},
                }
                tool_name = tool["name"]
                defs.append({
                    "name": tool_name,
                    "description": tool.get("description", f"MCP: {name}/{tool_name}"),
                    "input_schema": schema,
                })
                self._tool_map[tool_name] = name
        return defs, self._tool_map

    @property
    def started_servers(self) -> set[str]:
        return set(self._clients.keys())

    def is_mcp_tool(self, tool_name: str) -> bool:
        return tool_name in self._tool_map

    def execute(self, tool_name: str, arguments: dict) -> str | None:
        """Execute an MCP tool. Returns None if the tool is not from any managed server."""
        server = self._tool_map.get(tool_name)
        if not server:
            return None
        client = self._clients.get(server)
        if not client:
            return f"MCP server '{server}' 未连接"
        return client.call_tool(tool_name, arguments)

    def shutdown(self) -> None:
        for client in self._clients.values():
            client.stop()
        self._clients.clear()
        self._tool_map.clear()

    def _ensure(self, name: str) -> McpClient | McpHttpClient | None:
        if name in self._clients:
            return self._clients[name]
        cfg = self._configs.get(name)
        if not cfg:
            return None
        if cfg.get("type") == "http":
            client = McpHttpClient(name, cfg)
        else:
            client = McpClient(name, cfg)
        if client.start():
            self._clients[name] = client
            return client
        return None
