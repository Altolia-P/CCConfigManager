"""Core config item routes — browse, search, edit, move, stats, logs, MCP tools."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

from ..registry import TYPE_MAP, ALL_TYPES, CLAUDE_DIR, scanner, mover, get_static_dir
from .. import mcp_tools

STATIC_DIR = get_static_dir()

router = APIRouter(tags=["items"])


@router.get("/")
def index():
    dist_index = os.path.join(STATIC_DIR, "dist", "index.html")
    if os.path.isfile(dist_index):
        return FileResponse(dist_index)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@router.get("/api/types")
def get_types():
    return ALL_TYPES


@router.get("/api/items")
def get_items(
    type: str = Query(default="skills"),
    source: str = Query(default=""),
    status: str = Query(default="active"),
    search: str = Query(default=""),
):
    item_type = TYPE_MAP.get(type, type)
    all_items = scanner.scan_all()
    filtered = [i for i in all_items if i.type == item_type]
    if source:
        filtered = [i for i in filtered if i.source == source]
    if status:
        filtered = [i for i in filtered if i.status == status]
    if search:
        q = search.lower()
        filtered = [i for i in filtered if q in i.name.lower() or q in i.description.lower()]
    return filtered


def _prefer_active(items: list) -> list:
    """Sort item list so active items come first (for indeterminate selection)."""
    return sorted(items, key=lambda i: 0 if i.status == "active" else 1)


@router.get("/api/item/{item_type}/{name:path}")
def get_item(item_type: str, name: str):
    item_type = TYPE_MAP.get(item_type, item_type)
    all_items = scanner.scan_all()
    matches = [i for i in all_items if i.type == item_type and i.name == name]
    if matches:
        return _prefer_active(matches)[0]
    return JSONResponse({"success": False, "message": f"未找到: {item_type}/{name}"}, status_code=404)


@router.post("/api/items/batch")
def batch_items(body: dict):
    requested = body.get("items", [])
    if not requested:
        return []
    all_items = scanner.scan_all()
    idx: dict[tuple[str, str], list] = {}
    for item in all_items:
        idx.setdefault((item.type, item.name), []).append(item)
    result = []
    for r in requested:
        t = TYPE_MAP.get(r.get("type", ""), r.get("type", ""))
        n = r.get("name", "")
        if (t, n) in idx:
            result.append(_prefer_active(idx[(t, n)])[0])
    return result


@router.post("/api/move")
def move_item(body: dict):
    item_type = TYPE_MAP.get(body.get("type", ""), body.get("type", ""))
    name = body.get("name", "")
    to_status = body.get("to", "")
    all_items = scanner.scan_all()
    matches = [i for i in all_items if i.type == item_type and i.name == name]
    if not matches:
        return {"success": False, "message": f"未找到: {item_type}/{name}"}
    target = _prefer_active(matches)[0]
    scanner.invalidate_cache()
    return mover.move(target.path, item_type, name, to_status)


@router.get("/api/stats")
def get_stats():
    all_items = scanner.scan_all()
    stats: dict[str, dict[str, int]] = {}
    for item in all_items:
        stats.setdefault(item.type, {}).setdefault(item.status, 0)
        stats[item.type][item.status] += 1
    return stats


@router.get("/api/logs")
def get_logs(limit: int = Query(default=50)):
    return mover.get_logs(limit)


MAX_FILE_ENTRIES = 200

@router.get("/api/notifications")
def get_notifications(limit: int = Query(default=30)):
    nf = Path(os.path.expanduser("~/.claude/CCConfigManager/notifications.jsonl"))
    if not nf.is_file():
        return {"notifications": []}
    try:
        lines = nf.read_text(encoding="utf-8").strip().split("\n")
        # Truncate old entries to prevent unbounded growth
        if len(lines) > MAX_FILE_ENTRIES:
            nf.write_text("\n".join(lines[-MAX_FILE_ENTRIES:]) + "\n", encoding="utf-8")
            lines = lines[-MAX_FILE_ENTRIES:]
        items = []
        for line in lines[-limit:]:
            try:
                items.append(json.loads(line))
            except Exception:
                pass
        return {"notifications": list(reversed(items))}
    except Exception:
        return {"notifications": []}


@router.get("/api/tasks")
def get_tasks(limit: int = Query(default=30)):
    tf = Path(os.path.expanduser("~/.claude/CCConfigManager/agent-tasks.jsonl"))
    if not tf.is_file():
        return {"tasks": []}
    try:
        lines = tf.read_text(encoding="utf-8").strip().split("\n")
        # Truncate old entries to prevent unbounded growth
        if len(lines) > MAX_FILE_ENTRIES:
            tf.write_text("\n".join(lines[-MAX_FILE_ENTRIES:]) + "\n", encoding="utf-8")
            lines = lines[-MAX_FILE_ENTRIES:]
        items = []
        for line in lines:
            try:
                task = json.loads(line)
                if "id" not in task:
                    task["id"] = str(len(items))
                items.append(task)
            except Exception:
                pass
        return {"tasks": items[-limit:]}
    except Exception:
        return {"tasks": []}


@router.post("/api/mcp/refresh-tools")
def refresh_tools():
    import threading
    def _bg_refresh():
        mcp_tools.discover_and_cache(CLAUDE_DIR, force=True)
    threading.Thread(target=_bg_refresh, daemon=True).start()
    return {"success": True, "message": "后台刷新中，请稍后查看 Tools 列表"}


@router.put("/api/item/{item_type}/{name:path}")
def update_item(item_type: str, name: str, body: dict):
    item_type = TYPE_MAP.get(item_type, item_type)
    content = body.get("content")
    description = body.get("description")
    all_items = scanner.scan_all()
    matches = [i for i in all_items if i.type == item_type and i.name == name]
    if not matches:
        return {"success": False, "message": f"未找到: {item_type}/{name}"}
    target = _prefer_active(matches)[0]

    if item_type == "mcp":
        return _update_mcp(name, description or "", content or "")
    if item_type == "workflow":
        return _update_workflow(target.path, description or "", content or "")
    if item_type == "hook":
        return {"success": False, "message": "Hook 配置通过 hooks.json 管理，请直接编辑 JSON 文件"}
    if item_type == "tool":
        return {"success": False, "message": "Tool 由 MCP 服务器自动发现，无法手动编辑"}

    fp = Path(target.path)
    file_path = fp / "SKILL.md" if item_type == "skill" else fp
    try:
        if content is not None:
            file_path.write_text(content, encoding="utf-8")
        elif description is not None and description.strip():
            _update_file_description(file_path, description)
        scanner.invalidate_cache()
        return {"success": True, "message": "已保存"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# --- Helpers ---

def _update_workflow(file_path: str, description: str, content: str) -> dict:
    fp = Path(file_path)
    if not fp.is_file():
        return {"success": False, "message": "文件不存在"}
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"JSON 解析失败: {e}"}
    if content:
        try:
            new_data = json.loads(content)
            data["nodes"] = new_data.get("nodes", data.get("nodes", []))
            data["edges"] = new_data.get("edges", data.get("edges", []))
            for key in ("mode", "name", "slug", "description"):
                if key in new_data:
                    data[key] = new_data[key]
            data.pop("steps", None)
            data.pop("phases", None)
        except Exception:
            return {"success": False, "message": "内容不是有效 JSON"}
    if description:
        data["description"] = description
    try:
        fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": "已保存"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _update_mcp(name: str, description: str, content: str) -> dict:
    mcp_file = Path(os.path.expanduser("~/.claude/mcp-configs/mcp-servers.json"))
    if not mcp_file.is_file():
        return {"success": False, "message": "MCP 配置文件不存在"}
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"读取 MCP 配置失败: {e}"}
    if name not in data.get("mcpServers", {}):
        return {"success": False, "message": f"未找到 MCP server: {name}"}
    if description:
        data["mcpServers"][name]["description"] = description
    try:
        mcp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        scanner.invalidate_cache()
        return {"success": True, "message": "MCP 描述已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _update_file_description(file_path: Path, description: str) -> None:
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    in_frontmatter = False
    fm_dashes = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "---":
            fm_dashes += 1
            if fm_dashes == 1:
                in_frontmatter = True
                continue
            elif in_frontmatter:
                in_frontmatter = False
                continue
        if in_frontmatter:
            continue
        if stripped and not stripped.startswith("#"):
            lines[i] = description
            break
    file_path.write_text("\n".join(lines), encoding="utf-8")
