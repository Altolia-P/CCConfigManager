"""Hook executor — runs shell commands or agent calls at node entry/exit."""

import os
import subprocess
from .sandbox import Sandbox


def execute(hooks: list[dict], timing: str, project_path: str,
            prev_output: str = "", node_context: dict | None = None) -> list[dict]:
    """Execute hooks for given timing. node_context carries skill_ids/mcp_ids/tool_ids/permissions from the node."""
    results = []
    for hook in hooks:
        cfg = hook.get("hookConfig") or hook
        if cfg.get("timing") != timing:
            continue

        if cfg.get("type") == "shell":
            result = _run_shell(cfg, project_path, prev_output)
            results.append(result)
            if not result.get("success"):
                raise HookFailed(f"Hook 执行失败: {cfg.get('value', '')[:50]}\n{result.get('output', '')}")

        elif cfg.get("type") == "agent":
            result = _run_agent(cfg, project_path, prev_output, node_context)
            results.append(result)
            if not result.get("success"):
                raise HookFailed(f"Agent Hook 执行失败: {cfg.get('value', '')[:50]}\n{result.get('output', '')}")

    return results


def _run_shell(cfg: dict, project_path: str, prev_output: str = "") -> dict:
    command = cfg.get("value", "")
    cwd = cfg.get("cwd") or project_path
    env_override = cfg.get("env") or {}
    timeout = cfg.get("timeout") or 300

    try:
        result = subprocess.run(
            command, shell=True, cwd=cwd,
            env={**os.environ, **env_override,
                 "WF_PREV_OUTPUT": prev_output,
                 "WF_PROJECT_PATH": project_path},
            capture_output=True, text=True, timeout=timeout, encoding="utf-8",
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return {
            "success": result.returncode == 0,
            "output": output,
            "exit_code": result.returncode,
            "node_id": cfg.get("_node_id", ""),
            "timing": cfg.get("timing", ""),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"超时 ({timeout}s)", "exit_code": -1}
    except Exception as e:
        return {"success": False, "output": str(e), "exit_code": -1}


def _run_agent(cfg: dict, project_path: str, prev_output: str,
              node_context: dict | None = None) -> dict:
    agent_name = cfg.get("value", "")
    sandbox = Sandbox(project_path)
    ctx = node_context or {}
    try:
        from .agent_runner import run as agent_run
        output = agent_run(
            agent_id=agent_name,
            skill_ids=ctx.get("skill_ids", []),
            mcp_ids=ctx.get("mcp_ids", []),
            tool_ids=ctx.get("tool_ids", []),
            node_permissions=ctx.get("permissions"),
            user_message=prev_output + "\n\n执行 Hook agent 任务: " + agent_name,
            sandbox=sandbox,
        )
        return {"success": True, "output": output}
    except Exception as e:
        return {"success": False, "output": str(e)}


class HookFailed(Exception):
    pass
