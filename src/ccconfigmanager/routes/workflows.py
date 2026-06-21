"""Workflow routes — CRUD, create, copy, delete, migrate, export, import."""

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import Response, JSONResponse

from ..registry import CLAUDE_DIR
from .. import packs as packs_data

router = APIRouter(tags=["workflows"])


def _workflow_dir() -> Path:
    return Path(CLAUDE_DIR) / "workflows"


def _safe_name(name: str) -> str:
    """Reject path traversal and unsafe characters in workflow slugs."""
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"非法工作流名称: {name}")
    return name


def _safe_wf_path(name: str) -> Path:
    fp = (_workflow_dir() / f"{_safe_name(name)}.json").resolve()
    if not str(fp).startswith(str(_workflow_dir().resolve())):
        raise ValueError(f"路径越界: {name}")
    return fp


@router.delete("/api/workflows/{name}")
def delete(name: str):
    try:
        fp = _safe_wf_path(name)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    if not fp.is_file():
        return {"success": False, "message": "工作流不存在"}
    try:
        fp.unlink()
        return {"success": True, "message": f"已删除: {name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/workflows/{name}/copy")
def copy(name: str, body: dict = None):
    body = body or {}
    wf_dir = _workflow_dir()
    try:
        src = _safe_wf_path(name)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    if not src.is_file():
        return {"success": False, "message": "工作流不存在"}
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"JSON 解析失败: {e}"}

    new_name = body.get("name", "").strip() or f"{data.get('name', name)} (副本)"
    slug = body.get("slug", "").strip() or re.sub(
        r'[^a-z0-9-]', '', new_name.lower().replace(' ', '-').replace('_', '-')
    )[:50] or "copy"

    orig_slug = slug
    counter = 2
    while (wf_dir / f"{slug}.json").is_file():
        slug = f"{orig_slug}-{counter}"
        counter += 1

    data["name"] = new_name
    data["slug"] = slug
    data.pop("createdAt", None)
    data["copiedAt"] = __import__('datetime').datetime.utcnow().isoformat() + "Z"

    try:
        (wf_dir / f"{slug}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": f"已复制: {slug}", "slug": slug}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/workflows/create")
def create(body: dict):
    name = body.get("name", "").strip()
    mode = body.get("mode", "auto")
    if not name:
        return {"success": False, "message": "名称不能为空"}
    slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-').replace('_', '-'))[:50] or "new-workflow"
    wf_dir = _workflow_dir()
    wf_dir.mkdir(parents=True, exist_ok=True)
    fp = wf_dir / f"{slug}.json"
    if fp.exists():
        return {"success": False, "message": f"工作流 {slug} 已存在"}
    data = {
        "slug": slug, "name": name,
        "description": body.get("description", ""),
        "mode": mode,
        "nodes": body.get("nodes") or [],
        "edges": body.get("edges") or [],
        "createdAt": __import__('datetime').datetime.utcnow().isoformat() + "Z"
    }
    try:
        fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": f"已创建: {slug}", "slug": slug}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/api/migrate-workflows")
def migrate(body: dict = None):
    body = body or {}
    force = body.get("force", False)
    wf_dir = _workflow_dir()
    if not wf_dir.is_dir():
        return {"success": False, "message": "workflows 目录不存在"}
    backup_dir = wf_dir / ".backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    migrated, skipped, errors = 0, 0, 0

    for entry in sorted(wf_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".json":
            continue
        try:
            data = json.loads(entry.read_text(encoding="utf-8"))
        except Exception:
            errors += 1; continue
        if "nodes" in data and not force:
            skipped += 1; continue
        if force and "nodes" in data and "edges" in data:
            is_step = data.get("mode") == "step"
            gate_ids = set()
            for e in data["edges"]:
                if e.get("manualAdvance") or e.get("autoDetect"):
                    gate_ids.add(e["to"])
            for n in data["nodes"]:
                if n.get("type") == "agent" and is_step and n["id"] in gate_ids:
                    n["type"] = "gate"
                    for e in data["edges"]:
                        if e["to"] == n["id"]:
                            n["gateConfig"] = {
                                "condition": "manual" if e.get("manualAdvance") else "auto",
                                "autoDetect": e.get("autoDetect") or "",
                                "manualAdvance": e.get("manualAdvance") or "",
                                "expression": ""
                            }
                            break
            shutil.copy2(str(entry), str(backup_dir / entry.name))
            entry.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            migrated += 1; continue

        nodes, edges = [], []
        is_step = "phases" in data and data["phases"]
        items = data["phases"] if is_step else data.get("steps", [])
        for i, item in enumerate(items):
            nid = item.get("id") or item.get("name") or f"n{i+1}"
            is_gate = is_step and (item.get("manualAdvance") or item.get("autoDetect"))
            nodes.append({
                "id": nid, "type": "gate" if is_gate else "agent",
                "label": item.get("label") or item.get("description") or f"Step {i+1}",
                "position": {"x": i * 280, "y": 0},
                "agentId": item.get("agentSlug"), "skillIds": [],
                "permissions": {"allows": item.get("allows", []), "blocks": item.get("blocks", [])}
                if is_step else {"allows": [], "blocks": []},
                "produces": item.get("produces", []), "hooks": [],
                "gateConfig": {"condition": "manual" if item.get("manualAdvance") else "auto",
                               "autoDetect": item.get("autoDetect") or "",
                               "manualAdvance": item.get("manualAdvance") or "", "expression": ""}
                if is_gate else None
            })
            if i > 0:
                prev_id = items[i-1].get("id") or items[i-1].get("name") or f"n{i}"
                edges.append({
                    "id": f"e{i}", "from": prev_id, "to": nid,
                    "condition": "manual" if item.get("manualAdvance") else (
                        "auto" if item.get("autoDetect") else "auto"),
                    "autoDetect": item.get("autoDetect"),
                    "manualAdvance": item.get("manualAdvance")
                })
        shutil.copy2(str(entry), str(backup_dir / entry.name))
        data["nodes"] = nodes; data["edges"] = edges
        data["mode"] = "step" if is_step else "auto"
        data.pop("steps", None); data.pop("phases", None)
        entry.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        migrated += 1

    return {"success": True,
            "message": f"迁移完成: {migrated} 个, 跳过 {skipped} (已是v2), 错误 {errors}",
            "migrated": migrated, "skipped": skipped, "errors": errors}


@router.get("/api/workflows/{name}/export")
def export(name: str):
    try:
        fp = _safe_wf_path(name)
    except ValueError as e:
        return JSONResponse({"success": False, "message": str(e)}, status_code=400)
    if not fp.is_file():
        return JSONResponse({"success": False, "message": "工作流不存在"}, status_code=404)
    content = fp.read_text(encoding="utf-8")
    return Response(content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}.json"'})


@router.post("/api/import")
async def import_file(file: UploadFile = File(...)):
    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {"success": False, "message": "JSON 解析失败"}

    wf_dir = _workflow_dir()
    wf_dir.mkdir(parents=True, exist_ok=True)

    if "nodes" in data or "edges" in data or "steps" in data or "phases" in data:
        slug = data.get("slug", "").strip()
        if not slug:
            name = data.get("name", "").strip() or file.filename.rsplit(".", 1)[0]
            slug = re.sub(r'[^a-z0-9-]', '', name.lower().replace(' ', '-').replace('_', '-'))[:50]
        if not slug:
            slug = "imported-workflow"
        orig = slug; n = 2
        while (wf_dir / f"{slug}.json").is_file():
            slug = f"{orig}-{n}"; n += 1
        data["slug"] = slug
        (wf_dir / f"{slug}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": f"已导入工作流: {slug}", "type": "workflow", "slug": slug}

    elif any(k in data for k in ["skills", "agents", "commands", "rules"]):
        name = data.get("name", "").strip() or file.filename.rsplit(".", 1)[0] or "imported-pack"
        packs_all = packs_data._load()
        packs_list = packs_all.setdefault("packs", {})
        orig = name; n = 2
        while name in packs_list:
            name = f"{orig}-{n}"; n += 1
        data["name"] = name
        packs_list[name] = data
        packs_data._save(packs_all)
        return {"success": True, "message": f"已导入配置包: {name}", "type": "pack", "name": name}

    return {"success": False, "message": "无法识别文件类型（需要工作流或配置包格式）"}
