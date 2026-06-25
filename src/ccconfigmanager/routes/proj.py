"""Project routes — project CRUD, discover, sync, copy-to-project."""

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter

from ..registry import scanner
from .. import projects as projects_data

router = APIRouter(tags=["projects"])


@router.get("/api/projects")
def list_all():
    return projects_data.list_all()


@router.get("/api/project-items")
def items(path: str = ""):
    if not path:
        return []
    return scanner.scan_project(path)


@router.post("/api/projects")
def create(body: dict):
    return projects_data.create(body.get("name", ""), body.get("path", ""))


@router.delete("/api/projects/{name}")
def delete(name: str):
    return projects_data.delete(name)


@router.post("/api/projects/{name}/items")
def add_item(name: str, body: dict):
    return projects_data.add_item(name, body.get("type", ""), body.get("item_name", ""))


@router.delete("/api/projects/{name}/items")
def remove_item(name: str, body: dict):
    return projects_data.remove_item(name, body.get("type", ""), body.get("item_name", ""))


@router.post("/api/projects/{name}/sync")
def sync(name: str):
    proj = projects_data.get(name)
    if not proj:
        return {"success": False, "message": f"项目 {name} 不存在"}
    scanned = scanner.scan_project(proj.get("path", ""))
    if not scanned:
        return {"success": False, "message": "项目路径不存在或无 .claude 目录"}
    by_type = {"skills": [], "agents": [], "commands": [], "rules": []}
    for item in scanned:
        key = item.type + "s"
        if key in by_type and item.name not in by_type[key]:
            by_type[key].append(item.name)
    data = projects_data._load()
    if name in data.get("projects", {}):
        for key in by_type:
            data["projects"][name][key] = sorted(by_type[key])
        projects_data._save(data)
        return {"success": True, "message": f"已同步 {sum(len(v) for v in by_type.values())} 项配置", "items": by_type}
    return {"success": False, "message": "同步失败"}


@router.post("/api/projects/{name}/discover")
def discover(name: str):
    proj = projects_data.get(name)
    if not proj:
        return {"success": False, "message": f"项目 {name} 不存在"}
    proj_path = Path(proj.get("path", ""))
    if not proj_path.is_dir():
        return {"success": False, "message": "项目路径不存在"}

    all_items = scanner.scan_all()
    name_index = {}
    for item in all_items:
        low = item.name.lower()
        if low not in name_index or len(item.name) < len(name_index[low].name):
            name_index[low] = item

    texts = []
    for f in sorted(proj_path.glob("*.md")):
        try:
            texts.append(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    claude_dir = proj_path / ".claude"
    if claude_dir.is_dir():
        for f in sorted(claude_dir.rglob("*")):
            if f.is_file() and f.suffix in (".md", ".json", ".yaml", ".yml", ".toml", ".txt"):
                try:
                    texts.append(f.read_text(encoding="utf-8"))
                except Exception:
                    pass

    discovered = {"skills": [], "agents": [], "commands": [], "rules": [], "mcps": [], "workflows": []}
    seen = set()
    all_text = "\n".join(texts)
    tokens = set(re.findall(r'[a-zA-Z][\w-]{2,}', all_text.lower()))

    for token in tokens:
        if token in name_index and token not in seen:
            item = name_index[token]
            key = item.type + "s"
            if key in discovered:
                discovered[key].append(item.name)
                seen.add(token)

    count = 0
    data = projects_data._load()
    if name in data.get("projects", {}):
        proj_data = data["projects"][name]
        for k in discovered:
            if k not in proj_data:
                proj_data[k] = []
        for key in discovered:
            existing = set(proj_data.get(key, []))
            for item_name in discovered[key]:
                if item_name not in existing:
                    proj_data[key].append(item_name)
                    count += 1
            proj_data[key] = sorted(proj_data[key])
        projects_data._save(data)

    total = sum(len(v) for v in discovered.values())
    return {"success": True, "message": f"发现 {total} 项配置（新增 {count}）", "discovered": discovered, "added": count}


@router.post("/api/projects/{name}/import-pack")
def import_pack(name: str, body: dict):
    """Bulk-add all items from a pack into a project."""
    pack_name = body.get("pack_name", "")
    if not pack_name:
        return {"success": False, "message": "缺少 pack_name"}

    from .. import packs as packs_data
    all_packs = packs_data.list_all()
    pack = all_packs.get(pack_name)
    if not pack:
        return {"success": False, "message": f"配置包 {pack_name} 不存在"}

    proj = projects_data.get(name)
    if not proj:
        return {"success": False, "message": f"项目 {name} 不存在"}

    data = projects_data._load()
    proj_data = data.get("projects", {}).get(name)
    if not proj_data:
        return {"success": False, "message": f"项目 {name} 不存在"}

    added = 0
    skipped = 0
    type_keys = ["skills", "agents", "commands", "rules", "mcps", "tools", "workflows"]
    for key in type_keys:
        for item_name in pack.get(key, []):
            if key not in proj_data:
                proj_data[key] = []
            if item_name in proj_data[key]:
                skipped += 1
                continue
            proj_data[key].append(item_name)
            added += 1

    projects_data._save(data)
    return {"success": True, "message": f"已添加 {added} 项配置（跳过 {skipped} 项已存在）", "added": added, "skipped": skipped}


@router.post("/api/copy-to-project")
def copy_to_project(body: dict):
    project_path = body.get("project_path", "")
    item_type = body.get("type", "")
    item_name = body.get("name", "")

    if not project_path or not item_type or not item_name:
        return {"success": False, "message": "缺少参数"}

    from ..registry import TYPE_MAP
    item_type = TYPE_MAP.get(item_type, item_type)

    try:
        resolved = Path(project_path).resolve()
        home = Path.home().resolve()
        resolved.relative_to(home)
    except (ValueError, OSError):
        return {"success": False, "message": "项目路径必须在用户目录下"}

    all_items = scanner.scan_all()
    source = None
    for item in all_items:
        if item.type == item_type and item.name == item_name:
            source = item
            break
    if source is None:
        return {"success": False, "message": f"未找到: {item_type}/{item_name}"}

    dest_dir = Path(project_path) / ".claude"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if item_type == "skill":
            dest = dest_dir / "skills" / Path(source.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copytree(source.path, str(dest))
        elif item_type == "rule":
            rel = Path(source.path).name
            dest = dest_dir / "rules" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(source.path, str(dest))
        else:
            key = item_type + "s"
            dest = dest_dir / key / Path(source.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(source.path, str(dest))
        return {"success": True, "message": f"已复制 {item_name} 到项目"}
    except Exception as e:
        return {"success": False, "message": str(e)}
