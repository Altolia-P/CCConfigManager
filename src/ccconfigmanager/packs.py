"""Trigger packs — user-curated bundles of config items."""
import json
import os
from pathlib import Path


def _file() -> Path:
    return Path(os.path.expanduser("~/.claude/CCConfigManager/packs.json"))


def _load() -> dict:
    f = _file()
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"packs": {}}


def _save(data: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_all() -> dict[str, dict]:
    return _load().get("packs", {})


def create(name: str) -> dict:
    data = _load()
    if name in data.get("packs", {}):
        return {"success": False, "message": f"包 {name} 已存在"}
    data.setdefault("packs", {})[name] = {"name": name, "skills": [], "agents": [], "commands": [], "rules": [], "mcps": [], "tools": [], "workflows": []}
    _save(data)
    return {"success": True, "message": f"已创建配置包: {name}"}


def delete(name: str) -> dict:
    data = _load()
    if name not in data.get("packs", {}):
        return {"success": False, "message": f"包 {name} 不存在"}
    del data["packs"][name]
    _save(data)
    return {"success": True, "message": f"已删除包: {name}"}


def add_item(pack_name: str, item_type: str, item_name: str) -> dict:
    data = _load()
    pack = data.get("packs", {}).get(pack_name)
    if not pack:
        return {"success": False, "message": f"包 {pack_name} 不存在"}
    key = item_type + "s"
    if key not in pack:
        pack[key] = []
    if item_name in pack[key]:
        return {"success": False, "message": f"{item_name} 已在包中"}
    pack[key].append(item_name)
    _save(data)
    return {"success": True, "message": f"已添加 {item_name} 到 {pack_name}"}


def remove_item(pack_name: str, item_type: str, item_name: str) -> dict:
    data = _load()
    pack = data.get("packs", {}).get(pack_name)
    if not pack:
        return {"success": False, "message": f"包 {pack_name} 不存在"}
    key = item_type + "s"
    if key in pack and item_name in pack[key]:
        pack[key].remove(item_name)
        _save(data)
        return {"success": True, "message": f"已从包中移除 {item_name}"}
    return {"success": False, "message": f"{item_name} 不在包中"}
