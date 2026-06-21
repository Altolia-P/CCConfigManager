"""Project manager — store and manage projects with associated config items."""
import json
import os
from pathlib import Path


def _file() -> Path:
    return Path(os.path.expanduser("~/.claude/CCConfigManager/projects.json"))


def _load() -> dict:
    f = _file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"projects": {}}


def _save(data: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_all() -> dict[str, dict]:
    return _load().get("projects", {})


def get(name: str) -> dict | None:
    return _load().get("projects", {}).get(name)


def create(name: str, path: str = "") -> dict:
    data = _load()
    if name in data.get("projects", {}):
        return {"success": False, "message": f"项目 {name} 已存在"}
    data.setdefault("projects", {})[name] = {
        "name": name,
        "path": path,
        "skills": [],
        "agents": [],
        "commands": [],
        "rules": [],
        "mcps": [],
        "tools": [],
        "workflows": [],
        "hooks": [],
    }
    _save(data)
    return {"success": True, "message": f"已创建项目: {name}"}


def delete(name: str) -> dict:
    data = _load()
    if name not in data.get("projects", {}):
        return {"success": False, "message": f"项目 {name} 不存在"}
    del data["projects"][name]
    _save(data)
    return {"success": True, "message": f"已删除项目: {name}"}


def add_item(project_name: str, item_type: str, item_name: str) -> dict:
    data = _load()
    proj = data.get("projects", {}).get(project_name)
    if not proj:
        return {"success": False, "message": f"项目 {project_name} 不存在"}

    key = item_type + "s"
    if key not in proj:
        proj[key] = []
    if item_name in proj[key]:
        return {"success": False, "message": f"{item_name} 已在项目中"}
    proj[key].append(item_name)
    _save(data)
    return {"success": True, "message": f"已添加 {item_name} 到 {project_name}"}


def remove_item(project_name: str, item_type: str, item_name: str) -> dict:
    data = _load()
    proj = data.get("projects", {}).get(project_name)
    if not proj:
        return {"success": False, "message": f"项目 {project_name} 不存在"}
    key = item_type + "s"
    if key in proj and item_name in proj[key]:
        proj[key].remove(item_name)
        _save(data)
        return {"success": True, "message": f"已移除 {item_name}"}
    return {"success": False, "message": f"{item_name} 不在项目中"}
