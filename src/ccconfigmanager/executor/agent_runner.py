"""Agent runner — executes a single workflow node via Anthropic API."""

import json
import os
import threading
import yaml
from pathlib import Path

from anthropic import Anthropic

from . import tools as agent_tools
from .mcp_client import McpManager
from .permissions import filter_tools, is_tool_allowed
from .sandbox import Sandbox

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOOL_ROUNDS = 30
DEFAULT_TIMEOUT_MINUTES = 10

AGENT_CONFIG_PATH = Path(os.path.expanduser("~/.claude/CCConfigManager/agent-config.json"))
CLAUDE_DIR = Path(os.path.expanduser("~/.claude"))
ASQ_CHECKPOINT_DIR = Path(os.path.expanduser("~/.claude/CCConfigManager/asq-checkpoints"))

ASK_QUESTION_MARKER = "[WORKFLOW_ASK_USER_QUESTION]"


def _load_agent_config() -> dict:
    if not AGENT_CONFIG_PATH.is_file():
        return {}
    try:
        text = AGENT_CONFIG_PATH.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _get_agent_cfg(agent_name: str) -> dict:
    cfg = _load_agent_config()
    return cfg.get(agent_name, {})


def _get_api_key(agent_name: str) -> str:
    agent_cfg = _get_agent_cfg(agent_name)
    api_key = agent_cfg.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise ValueError(
            f"未配置 Anthropic API Key（agent: {agent_name}）。\n"
            "解决方法：\n"
            "1. 在侧边栏 ⚙ Agent 配置 → 选择 {agent_name} → 填入 API Key\n"
            "2. 或设置环境变量: export ANTHROPIC_API_KEY=sk-ant-..."
        )
    return api_key


def _get_model(agent_name: str) -> str:
    agent_cfg = _get_agent_cfg(agent_name)
    return agent_cfg.get("model") or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def _get_base_url(agent_name: str) -> str | None:
    agent_cfg = _get_agent_cfg(agent_name)
    return agent_cfg.get("base_url") or os.environ.get("ANTHROPIC_BASE_URL") or None


def _parse_agent_md(agent_name: str) -> dict:
    agent_file = CLAUDE_DIR / "agents" / f"{agent_name}.md"
    if not agent_file.is_file():
        raise FileNotFoundError(f"Agent 文件不存在: {agent_file}")

    text = agent_file.read_text(encoding="utf-8")
    # Parse YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1]) or {}
            system_prompt = parts[2].strip()
        else:
            frontmatter = {}
            system_prompt = text.strip()
    else:
        frontmatter = {}
        system_prompt = text.strip()

    agent_cfg = _get_agent_cfg(agent_name)
    # Priority: agent-config.json > env ANTHROPIC_MODEL > YAML frontmatter > DEFAULT_MODEL
    model = agent_cfg.get("model") or os.environ.get("ANTHROPIC_MODEL") or frontmatter.get("model") or DEFAULT_MODEL
    return {
        "name": agent_name,
        "system_prompt": system_prompt,
        "tools": frontmatter.get("tools", []),
        "model": model,
        "api_key": _get_api_key(agent_name),
    }


def _load_skill_content(skill_name: str) -> str:
    skill_md = CLAUDE_DIR / "skills" / skill_name / "SKILL.md"
    if skill_md.is_file():
        return skill_md.read_text(encoding="utf-8")
    return ""


def run(agent_id: str, skill_ids: list[str], mcp_ids: list[str], tool_ids: list[str],
        node_permissions: dict | None, user_message: str, sandbox: Sandbox,
        max_rounds: int = MAX_TOOL_ROUNDS, timeout_minutes: float = DEFAULT_TIMEOUT_MINUTES,
        run_id: str = "") -> str:
    """Execute a single agent node and return final text output.

    timeout_minutes: wall-clock timeout for this node (default 10 min). After timeout,
    the agent loop exits gracefully on the next iteration boundary.
    """

    agent_def = _parse_agent_md(agent_id)
    system_prompt = agent_def["system_prompt"]

    # Inject skill contents into system prompt
    if skill_ids:
        skill_texts = []
        for sid in skill_ids:
            content = _load_skill_content(sid)
            if content:
                skill_texts.append(f"<skill name=\"{sid}\">\n{content}\n</skill>")
        if skill_texts:
            system_prompt += "\n\n" + "\n".join(skill_texts)

    # Merge agent's declared tools + node's toolIds, then filter through permissions
    merged_tools = list(dict.fromkeys((agent_def["tools"] or []) + (tool_ids or [])))
    allowed_tools = filter_tools(merged_tools, node_permissions)

    # Build Anthropic tool definitions (built-in)
    tool_defs = _build_tool_defs(allowed_tools)

    base_url = _get_base_url(agent_id)
    client_kwargs = {"api_key": agent_def["api_key"]}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = Anthropic(**client_kwargs)

    messages = [{"role": "user", "content": user_message}]
    text_output: list[str] = []

    # Start MCP servers and discover their tools (McpManager itself is cheap until get_tool_defs starts servers)
    mcp_manager = McpManager()
    if mcp_ids:
        mcp_tool_defs = mcp_manager.get_tool_defs(mcp_ids)[0]
        started = mcp_manager.started_servers
        failed = [m for m in mcp_ids if m not in started]
        if mcp_tool_defs:
            tool_defs = tool_defs + mcp_tool_defs
            system_prompt += f"\n\n可用的 MCP 工具来自: {', '.join(sorted(started))}"
        if failed:
            warning = f"\n⚠ MCP server 启动失败（已跳过）: {', '.join(failed)}。请检查 mcp-servers.json 中的配置。"
            text_output.append(warning)
            system_prompt += warning

    # Timeout watchdog
    timed_out = threading.Event()
    timeout_seconds = timeout_minutes * 60
    start_time = __import__('time').time()
    watchdog = threading.Timer(timeout_seconds, timed_out.set)
    watchdog.daemon = True
    watchdog.start()

    try:
        for round_num in range(max_rounds):
            if timed_out.is_set():
                text_output.append(f"\n[节点超时: {timeout_minutes} 分钟]")
                break

            response = client.messages.create(
                model=agent_def["model"],
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
                tools=tool_defs if tool_defs else None,
                thinking={"type": "disabled"},
            )

            assistant_content = []
            has_tool_use = False

            for block in response.content:
                if block.type == "text":
                    text_output.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    has_tool_use = True
                    tool_name = block.name
                    tool_input = block.input

                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    # Execute tool — MCP first, then built-in handlers
                    if is_tool_allowed(tool_name, tool_input, node_permissions):
                        try:
                            if mcp_manager.is_mcp_tool(tool_name):
                                result = mcp_manager.execute(tool_name, tool_input)
                            else:
                                result = agent_tools.execute(tool_name, tool_input, sandbox)
                        except agent_tools.AskUserQuestionSignal as asq:
                            ckpt_id = f"asq-{run_id}-{round_num}" if run_id else f"asq-{round_num}"
                            _save_asq_checkpoint(ckpt_id, {
                                "messages": messages,
                                "assistant_content": assistant_content,
                                "tool_use_id": block.id,
                                "tool_name": tool_name,
                                "system_prompt": system_prompt,
                                "tool_defs": tool_defs,
                                "model": agent_def["model"],
                                "api_key": agent_def["api_key"],
                                "base_url": base_url,
                                "round_num": round_num,
                                "max_rounds": max_rounds,
                                "timeout_remaining": max(1, int(timeout_seconds - (__import__('time').time() - start_time))),
                                "mcp_ids": mcp_ids,
                                "node_permissions": node_permissions,
                            })
                            mcp_manager.shutdown()
                            question_data = {
                                "run_id": run_id,
                                "question": asq.question,
                                "header": asq.header,
                                "options": asq.options,
                                "checkpoint_id": ckpt_id,
                            }
                            return f"{ASK_QUESTION_MARKER}\n{json.dumps(question_data, ensure_ascii=False)}"
                        except Exception as tool_err:
                            result = f"工具调用失败: {tool_err}\n请检查参数并重试，或改用其他方式完成任务。"
                    else:
                        result = f"工具 {tool_name} 被权限禁止调用"

                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }]
                    })
                    assistant_content = []
                elif block.type in ("thinking", "redacted_thinking"):
                    # Serialize the block exactly as the API returned it
                    try:
                        assistant_content.append(block.model_dump())
                    except AttributeError:
                        assistant_content.append({
                            "type": block.type,
                            "thinking": getattr(block, "thinking", ""),
                            "signature": getattr(block, "signature", ""),
                        })

            if not has_tool_use:
                messages.append({"role": "assistant", "content": assistant_content})
                break
        else:
            text_output.append("\n[达到最大轮次限制]")
    finally:
        watchdog.cancel()
        mcp_manager.shutdown()

    return "\n".join(text_output)




def _build_tool_defs(tool_names: list[str]) -> list[dict]:
    """Build Anthropic-compatible tool definitions for known tools."""
    tool_map = {
        "Read": {"name": "Read", "description": "Read content of a file", "input_schema": {
            "type": "object", "properties": {"file_path": {"type": "string", "description": "Path to the file"}},
            "required": ["file_path"]}},
        "Write": {"name": "Write", "description": "Write content to a file", "input_schema": {
            "type": "object", "properties": {
                "file_path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"}},
            "required": ["file_path", "content"]}},
        "Edit": {"name": "Edit", "description": "Edit a file with string replacement", "input_schema": {
            "type": "object", "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit"},
                "old_string": {"type": "string", "description": "The exact text to replace"},
                "new_string": {"type": "string", "description": "The text to replace it with"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"}},
            "required": ["file_path", "old_string", "new_string"]}},
        "Bash": {"name": "Bash", "description": "Execute a shell command", "input_schema": {
            "type": "object", "properties": {"command": {"type": "string", "description": "Shell command to execute"},
                                               "timeout": {"type": "integer", "description": "Timeout in seconds"}},
            "required": ["command"]}},
        "Skill": {"name": "Skill", "description": "Invoke a registered skill", "input_schema": {
            "type": "object", "properties": {
                "skill": {"type": "string", "description": "The skill name to invoke"},
                "args": {"type": "string", "description": "Optional arguments for the skill"}},
            "required": ["skill"]}},
        "WebFetch": {"name": "WebFetch", "description": "Fetch content from a URL", "input_schema": {
            "type": "object", "properties": {"url": {"type": "string", "description": "URL to fetch"}},
            "required": ["url"]}},
        "WebSearch": {"name": "WebSearch", "description": "Search the web for information", "input_schema": {
            "type": "object", "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"]}},
        "TaskCreate": {"name": "TaskCreate", "description": "Create a new task item", "input_schema": {
            "type": "object", "properties": {
                "subject": {"type": "string", "description": "Task title/subject"},
                "description": {"type": "string", "description": "What needs to be done"}},
            "required": ["subject", "description"]}},
        "TaskUpdate": {"name": "TaskUpdate", "description": "Update task status", "input_schema": {
            "type": "object", "properties": {
                "task_id": {"type": "string", "description": "Task ID to update"},
                "status": {"type": "string", "description": "New status (pending/in_progress/completed/deleted)"}},
            "required": ["task_id"]}},
        "Glob": {"name": "Glob", "description": "Find files matching a glob pattern", "input_schema": {
            "type": "object", "properties": {"pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.ts)"}},
            "required": ["pattern"]}},
        "Grep": {"name": "Grep", "description": "Search for a regex pattern in files", "input_schema": {
            "type": "object", "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "directory": {"type": "string", "description": "Directory to search in"}},
            "required": ["pattern"]}},
        "PushNotification": {"name": "PushNotification", "description": "Send a push notification", "input_schema": {
            "type": "object", "properties": {"message": {"type": "string", "description": "Notification message to send"}},
            "required": ["message"]}},
        "AskUserQuestion": {"name": "AskUserQuestion", "description": "Ask the user a question and get their answer", "input_schema": {
            "type": "object", "properties": {
                "question": {"type": "string", "description": "The question to ask the user"},
                "header": {"type": "string", "description": "Short header label for the question"},
                "options": {"type": "array", "description": "Optional list of choices for the user", "items": {"type": "object", "properties": {
                    "label": {"type": "string", "description": "Display text for this option"},
                    "description": {"type": "string", "description": "Explanation of what this option means"}
                }}}},
            "required": ["question"]}},
    }
    return [tool_map[t] for t in tool_names if t in tool_map]


def save_agent_config(agent_name: str, config: dict) -> None:
    """Save per-agent config (model, api_key)."""
    cfg = _load_agent_config()
    cfg[agent_name] = config
    AGENT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_agent_config(agent_name: str) -> dict:
    return _load_agent_config().get(agent_name, {})


def _save_asq_checkpoint(checkpoint_id: str, state: dict) -> None:
    """Save agent state so execution can resume after user answers."""
    ASQ_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    fp = ASQ_CHECKPOINT_DIR / f"{checkpoint_id}.json"
    # Serialize messages — convert dicts to JSON-safe structure
    serializable = {
        "messages": state["messages"],
        "assistant_content": state["assistant_content"],
        "tool_use_id": state["tool_use_id"],
        "tool_name": state["tool_name"],
        "system_prompt": state["system_prompt"],
        "tool_defs": state["tool_defs"],
        "model": state["model"],
        "api_key": state["api_key"],
        "base_url": state["base_url"],
        "round_num": state["round_num"],
        "max_rounds": state["max_rounds"],
        "timeout_remaining": state["timeout_remaining"],
        "mcp_ids": state["mcp_ids"],
        "node_permissions": state["node_permissions"],
    }
    fp.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")


def resume_from_question(checkpoint_id: str, user_answer: str, sandbox: Sandbox) -> str:
    """Resume agent execution after the user answers a question."""
    fp = ASQ_CHECKPOINT_DIR / f"{checkpoint_id}.json"
    if not fp.is_file():
        return f"Error: checkpoint not found: {checkpoint_id}"

    state = json.loads(fp.read_text(encoding="utf-8"))

    messages = state["messages"]
    assistant_content = state["assistant_content"]
    tool_use_id = state["tool_use_id"]
    system_prompt = state["system_prompt"]
    tool_defs = state["tool_defs"]
    model = state["model"]
    api_key = state["api_key"]
    base_url = state["base_url"]
    round_num = state["round_num"]
    max_rounds = state["max_rounds"]
    mcp_ids = state["mcp_ids"]
    node_permissions = state["node_permissions"]

    # Inject the answer as a tool_result
    messages.append({"role": "assistant", "content": assistant_content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": user_answer,
        }]
    })
    assistant_content = []

    # Restart MCP
    mcp_manager = McpManager()
    if mcp_ids:
        mcp_tool_defs = mcp_manager.get_tool_defs(mcp_ids)[0]

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = Anthropic(**client_kwargs)

    timed_out = threading.Event()
    remaining = state.get("timeout_remaining", 600)
    watchdog = threading.Timer(remaining, timed_out.set)
    watchdog.daemon = True
    watchdog.start()

    text_output = []

    try:
        for r in range(round_num, max_rounds):
            if timed_out.is_set():
                text_output.append(f"\n[节点超时]")
                break

            response = client.messages.create(
                model=model,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
                tools=tool_defs if tool_defs else None,
                thinking={"type": "disabled"},
            )

            assistant_content = []
            has_tool_use = False

            for block in response.content:
                if block.type == "text":
                    text_output.append(block.text)
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    has_tool_use = True
                    tool_name = block.name
                    tool_input = block.input

                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    if is_tool_allowed(tool_name, tool_input, node_permissions):
                        try:
                            if mcp_manager.is_mcp_tool(tool_name):
                                result_tool = mcp_manager.execute(tool_name, tool_input)
                            else:
                                result_tool = agent_tools.execute(tool_name, tool_input, sandbox)
                        except agent_tools.AskUserQuestionSignal as asq:
                            ckpt_id = f"{checkpoint_id}-r{r}"
                            _save_asq_checkpoint(ckpt_id, {
                                "messages": messages,
                                "assistant_content": assistant_content,
                                "tool_use_id": block.id,
                                "tool_name": tool_name,
                                "system_prompt": system_prompt,
                                "tool_defs": tool_defs,
                                "model": model,
                                "api_key": api_key,
                                "base_url": base_url,
                                "round_num": r,
                                "max_rounds": max_rounds,
                                "timeout_remaining": remaining,
                                "mcp_ids": mcp_ids,
                                "node_permissions": node_permissions,
                            })
                            mcp_manager.shutdown()
                            question_data = {
                                "run_id": checkpoint_id.split("-r")[0] if "-r" in checkpoint_id else "",
                                "question": asq.question,
                                "header": asq.header,
                                "options": asq.options,
                                "checkpoint_id": ckpt_id,
                            }
                            return f"{ASK_QUESTION_MARKER}\n{json.dumps(question_data, ensure_ascii=False)}"
                        except Exception as tool_err:
                            result_tool = f"工具调用失败: {tool_err}\n请检查参数并重试，或改用其他方式完成任务。"
                    else:
                        result_tool = f"工具 {tool_name} 被权限禁止调用"

                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_tool,
                        }]
                    })
                    assistant_content = []
                elif block.type in ("thinking", "redacted_thinking"):
                    try:
                        assistant_content.append(block.model_dump())
                    except AttributeError:
                        assistant_content.append({
                            "type": block.type,
                            "thinking": getattr(block, "thinking", ""),
                            "signature": getattr(block, "signature", ""),
                        })

            if not has_tool_use:
                messages.append({"role": "assistant", "content": assistant_content})
                break
        else:
            text_output.append("\n[达到最大轮次限制]")
    finally:
        watchdog.cancel()
        mcp_manager.shutdown()
        try:
            fp.unlink()
        except Exception:
            pass

    return "\n".join(text_output)
