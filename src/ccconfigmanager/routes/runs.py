"""Workflow execution + run status routes."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..registry import CLAUDE_DIR, scanner
from ..executor import execute_async, continue_run, list_runs, get as get_run
from .. import projects as projects_data

router = APIRouter(tags=["runs"])


@router.post("/api/workflows/execute")
def execute(body: dict):
    workflow_name = body.get("workflow_slug", "")
    project_name = body.get("project_name", "")
    max_tool_rounds = body.get("max_tool_rounds", 30)
    initial_message = body.get("message", "") or ""

    if not workflow_name:
        return {"success": False, "message": "缺少 workflow_slug 参数"}

    if ".." in workflow_name or "/" in workflow_name or "\\" in workflow_name:
        return {"success": False, "message": f"非法工作流名称: {workflow_name}"}
    wf_file = (Path(CLAUDE_DIR) / "workflows" / f"{workflow_name}.json").resolve()
    if not str(wf_file).startswith(str((Path(CLAUDE_DIR) / "workflows").resolve())):
        return {"success": False, "message": f"路径越界: {workflow_name}"}
    if not wf_file.is_file():
        return {"success": False, "message": f"工作流不存在: {workflow_name}"}

    import json as _json
    try:
        workflow_json = _json.loads(wf_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"JSON 解析失败: {e}"}

    proj_path = os.getcwd()
    if project_name:
        proj = projects_data.get(project_name)
        if proj:
            proj_path = proj.get("path", os.getcwd())

    try:
        run_id = execute_async(workflow_json, project_name or "", proj_path,
                               max_tool_rounds, initial_message=initial_message)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "run_id": run_id, "status": "running"}


@router.get("/api/runs")
def all_runs(project: str = ""):
    return list_runs(project or None)


@router.get("/api/runs/{run_id}")
def detail(run_id: str):
    try:
        return {"success": True, "data": get_run(run_id)}
    except FileNotFoundError:
        return JSONResponse({"success": False, "message": "Run 不存在"}, status_code=404)


@router.post("/api/runs/{run_id}/approve")
def approve(run_id: str, body: dict = None):
    try:
        data = get_run(run_id)
        proj_path = data.get("project_path", os.getcwd())
        result = continue_run(run_id, proj_path)
        return {"success": True, "message": result}
    except FileNotFoundError:
        return JSONResponse({"success": False, "message": "Run 不存在"}, status_code=404)


@router.post("/api/runs/{run_id}/retry")
def retry(run_id: str):
    try:
        data = get_run(run_id)
        proj_path = data.get("project_path", os.getcwd())
        result = continue_run(run_id, proj_path)
        return {"success": True, "message": result}
    except FileNotFoundError:
        return JSONResponse({"success": False, "message": "Run 不存在"}, status_code=404)


@router.post("/api/runs/{run_id}/answer")
def answer(run_id: str, body: dict):
    """Answer an agent's AskUserQuestion during workflow execution."""
    user_answer = body.get("answer", "") if body else ""
    if not user_answer:
        return {"success": False, "message": "缺少 answer 参数"}
    try:
        data = get_run(run_id)
        proj_path = data.get("project_path", os.getcwd())
        result = continue_run(run_id, proj_path, user_answer=user_answer)
        return {"success": True, "message": result}
    except FileNotFoundError:
        return JSONResponse({"success": False, "message": "Run 不存在"}, status_code=404)


@router.post("/api/runs/{run_id}/cancel")
def cancel(run_id: str):
    from ..executor.run_store import update as run_update
    try:
        run_update(run_id, status="cancelled")
        return {"success": True, "message": "已取消"}
    except FileNotFoundError:
        return JSONResponse({"success": False, "message": "Run 不存在"}, status_code=404)


@router.get("/api/notifications")
def get_notifications(limit: int = 50):
    """Return recent push notifications from agent executions."""
    nf = Path(os.path.expanduser("~/.claude/CCConfigManager/notifications.jsonl"))
    if not nf.is_file():
        return {"success": True, "notifications": []}
    try:
        lines = nf.read_text(encoding="utf-8").strip().split("\n")
        items = []
        for line in lines[-limit:]:
            if line.strip():
                items.append(json.loads(line))
        return {"success": True, "notifications": list(reversed(items))}
    except Exception:
        return {"success": True, "notifications": []}


@router.get("/api/tasks")
def get_tasks(limit: int = 50):
    """Return agent-created tasks from workflow executions."""
    tf = Path(os.path.expanduser("~/.claude/CCConfigManager/agent-tasks.jsonl"))
    if not tf.is_file():
        return {"success": True, "tasks": []}
    try:
        lines = tf.read_text(encoding="utf-8").strip().split("\n")
        items = []
        for i, line in enumerate(lines):
            if line.strip():
                task = json.loads(line)
                task["id"] = str(i)
                items.append(task)
        return {"success": True, "tasks": list(reversed(items[-limit:]))}
    except Exception:
        return {"success": True, "tasks": []}


@router.post("/api/workflows/{name}/validate")
def validate(name: str):
    if ".." in name or "/" in name or "\\" in name:
        return {"success": False, "message": f"非法工作流名称: {name}"}
    wf_file = Path(CLAUDE_DIR) / "workflows" / f"{name}.json"
    if not wf_file.is_file():
        return {"success": False, "message": f"工作流不存在: {name}"}

    import json as _json
    wf = _json.loads(wf_file.read_text(encoding="utf-8"))

    issues = {"missing_agents": [], "missing_skills": [], "missing_mcps": []}
    all_items = [i for i in scanner.scan_all() if i.status == "active"]

    for node in wf.get("nodes", []):
        if node.get("agentId"):
            found = any(i.type == "agent" and i.name == node["agentId"] for i in all_items)
            if not found:
                issues["missing_agents"].append(node["agentId"])
        for sid in node.get("skillIds", []) or []:
            found = any(i.type == "skill" and i.name == sid for i in all_items)
            if not found:
                issues["missing_skills"].append(sid)
        for mid in node.get("mcpIds", []) or []:
            found = any(i.type == "mcp" and i.name == mid for i in all_items)
            if not found:
                issues["missing_mcps"].append(mid)

    total = sum(len(v) for v in issues.values())
    if total == 0:
        return {"success": True, "message": "所有引用均有效", "issues": issues}
    return {"success": False, "message": f"发现 {total} 个失效引用", "issues": issues}
