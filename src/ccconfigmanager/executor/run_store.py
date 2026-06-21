"""Run state persistence — stores execution progress as JSON files."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

RUNS_DIR = Path(os.path.expanduser("~/.claude/CCConfigManager/runs"))


def _file(run_id: str) -> Path:
    return RUNS_DIR / f"{run_id}.json"


def _load(run_id: str) -> dict:
    fp = _file(run_id)
    if not fp.is_file():
        raise FileNotFoundError(f"Run 不存在: {run_id}")
    return json.loads(fp.read_text(encoding="utf-8"))


def _save(run_id: str, data: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    _file(run_id).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def create(workflow_slug: str, project_name: str, project_path: str, nodes: list[str],
           initial_message: str = "") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"run-{ts}-{workflow_slug[:20]}"
    node_states = {}
    for nid in nodes:
        node_states[nid] = {"status": "pending", "output": None, "started_at": None, "finished_at": None}
    data = {
        "id": run_id, "workflow_slug": workflow_slug,
        "project_name": project_name, "project_path": project_path,
        "status": "running", "current_node": None,
        "nodes": node_states, "hook_results": [],
        "error": None, "initial_message": initial_message,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
    }
    _save(run_id, data)
    return run_id


VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "failed"},
    "running": {"completed", "failed", "waiting_approval", "waiting_confirmation", "waiting_question"},
    "waiting_approval": {"running", "failed", "completed"},
    "waiting_confirmation": {"running", "failed", "completed"},
    "waiting_question": {"running", "failed", "completed"},
    "completed": set(),
    "failed": {"running"},
}


def update(run_id: str, **kwargs) -> dict:
    data = _load(run_id)
    new_status = kwargs.get("status")
    if new_status and new_status != data.get("status"):
        allowed = VALID_TRANSITIONS.get(data.get("status", "pending"), set())
        if new_status not in allowed:
            raise ValueError(
                f"无效状态转换: {data.get('status')} → {new_status} "
                f"(允许: {', '.join(sorted(allowed)) or '无'})"
            )
    data.update(kwargs)
    _save(run_id, data)
    return data


def update_node(run_id: str, node_id: str, **kwargs) -> dict:
    data = _load(run_id)
    if node_id in data["nodes"]:
        data["nodes"][node_id].update(kwargs)
    else:
        import logging
        logging.getLogger("ccconfigmanager").warning(
            f"update_node: 未知节点 ID '{node_id}' (run={run_id}, "
            f"已知节点: {', '.join(data['nodes'].keys())})"
        )
    _save(run_id, data)
    return data


def set_pending_question(run_id: str, node_id: str, question_data: dict) -> dict:
    data = _load(run_id)
    question_data["node_id"] = node_id
    data["pending_question"] = question_data
    _save(run_id, data)
    return data


def clear_pending_question(run_id: str) -> dict:
    data = _load(run_id)
    data.pop("pending_question", None)
    _save(run_id, data)
    return data


def add_hook_result(run_id: str, result: dict) -> dict:
    data = _load(run_id)
    data.setdefault("hook_results", []).append(result)
    _save(run_id, data)
    return data


def add_produces_result(run_id: str, node_id: str, results: list[dict]) -> dict:
    data = _load(run_id)
    data.setdefault("produces_results", {})
    data["produces_results"][node_id] = results
    _save(run_id, data)
    return data


def complete(run_id: str) -> dict:
    return update(run_id, status="completed", finished_at=datetime.now(timezone.utc).isoformat())


def fail(run_id: str, reason: str) -> dict:
    return update(run_id, status="failed", error=reason, finished_at=datetime.now(timezone.utc).isoformat())


def get(run_id: str) -> dict:
    return _load(run_id)


def list_runs(project_name: str | None = None) -> list[dict]:
    if not RUNS_DIR.is_dir():
        return []
    runs = []
    for fp in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if project_name and data.get("project_name") != project_name:
                continue
            runs.append({
                "id": data["id"], "status": data["status"],
                "workflow_slug": data["workflow_slug"],
                "project_name": data.get("project_name"),
                "initial_message": data.get("initial_message"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "error": data.get("error"),
            })
        except Exception:
            pass
    return runs
