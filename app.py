import json
import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from scanner import Scanner
from source_detector import SourceDetector
from mover import Mover
import mcp_tools
import packs
import projects

CLAUDE_DIR = os.path.expanduser("~/.claude")

detector = SourceDetector(CLAUDE_DIR)
scanner = Scanner(CLAUDE_DIR, detector)
mover = Mover(CLAUDE_DIR)

_TYPE_MAP = {"skills": "skill", "agents": "agent", "commands": "command", "rules": "rule", "mcps": "mcp", "tools": "tool", "workflows": "workflow"}

app = FastAPI(title="Project Manager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/types")
def get_types():
    return ["skills", "agents", "commands", "rules", "mcps", "tools", "workflows"]


@app.get("/api/items")
def get_items(
    type: str = Query(default="skills"),
    source: str = Query(default=""),
    status: str = Query(default=""),
    search: str = Query(default=""),
):
    item_type = _TYPE_MAP.get(type, type)
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


@app.get("/api/item/{item_type}/{name:path}")
def get_item(item_type: str, name: str):
    item_type = _TYPE_MAP.get(item_type, item_type)
    all_items = scanner.scan_all()
    for item in all_items:
        if item.type == item_type and item.name == name:
            return item
    return None


@app.post("/api/move")
def move_item(body: dict):
    item_type = _TYPE_MAP.get(body.get("type", ""), body.get("type", ""))
    name = body.get("name", "")
    to_status = body.get("to", "")

    all_items = scanner.scan_all()
    target = None
    for item in all_items:
        if item.type == item_type and item.name == name:
            target = item
            break

    if target is None:
        return {"success": False, "message": f"未找到: {item_type}/{name}"}

    return mover.move(target.path, item_type, name, to_status)


@app.get("/api/stats")
def get_stats():
    all_items = scanner.scan_all()
    stats: dict[str, dict[str, int]] = {}
    for item in all_items:
        if item.type not in stats:
            stats[item.type] = {}
        st = stats[item.type]
        st[item.status] = st.get(item.status, 0) + 1
    return stats


@app.put("/api/item/{item_type}/{name:path}")
def update_item(item_type: str, name: str, body: dict):
    item_type = _TYPE_MAP.get(item_type, item_type)
    content = body.get("content", "")
    description = body.get("description", "")
    all_items = scanner.scan_all()
    for item in all_items:
        if item.type == item_type and item.name == name:
            target = item
            break
    else:
        return {"success": False, "message": f"未找到: {item_type}/{name}"}

    if item_type == "mcp":
        return _update_mcp_server(name, description, content)
    if item_type == "workflow":
        return _update_workflow(target.path, description, content)

    ip = Path(target.path)
    file_path = ip / "SKILL.md" if item_type == "skill" else ip
    try:
        file_path.write_text(content, encoding="utf-8")
        return {"success": True, "message": "已保存"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _update_workflow(file_path: str, description: str, content: str) -> dict:
    fp = Path(file_path)
    if not fp.is_file():
        return {"success": False, "message": "文件不存在"}
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"JSON 解析失败: {e}"}
    if description:
        data["description"] = description
    if content:
        try:
            data = json.loads(content)
        except Exception:
            return {"success": False, "message": "内容不是有效 JSON"}
    try:
        fp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": "已保存"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _update_mcp_server(name: str, description: str, content: str) -> dict:
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
    if content:
        data["mcpServers"][name]["description"] = content

    try:
        mcp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"success": True, "message": "MCP 描述已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/logs")
def get_logs(limit: int = Query(default=50)):
    return mover.get_logs(limit)


@app.post("/api/mcp/refresh-tools")
def refresh_tools():
    import threading
    def _bg_refresh():
        mcp_tools.discover_and_cache(CLAUDE_DIR, force=True)
    threading.Thread(target=_bg_refresh, daemon=True).start()
    return {"success": True, "message": "后台刷新中，请稍后查看 Tools 列表"}


@app.get("/api/projects")
def get_projects():
    return projects.list_all()


@app.get("/api/project-items")
def get_project_items(path: str = Query(default="")):
    if not path:
        return []
    return scanner.scan_project(path)


@app.post("/api/projects")
def create_project(body: dict):
    return projects.create(body.get("name", ""), body.get("path", ""))


@app.delete("/api/projects/{name}")
def delete_project(name: str):
    return projects.delete(name)


@app.post("/api/projects/{name}/items")
def add_project_item(name: str, body: dict):
    return projects.add_item(name, body.get("type", ""), body.get("item_name", ""))


@app.delete("/api/projects/{name}/items")
def remove_project_item(name: str, body: dict):
    return projects.remove_item(name, body.get("type", ""), body.get("item_name", ""))


@app.get("/api/packs")
def get_packs():
    return packs.list_all()


@app.post("/api/packs")
def create_pack(body: dict):
    return packs.create(body.get("name", ""))


@app.delete("/api/packs/{name}")
def delete_pack(name: str):
    return packs.delete(name)


@app.post("/api/packs/{name}/items")
def add_pack_item(name: str, body: dict):
    return packs.add_item(name, body.get("type", ""), body.get("item_name", ""))


@app.delete("/api/packs/{name}/items")
def remove_pack_item(name: str, body: dict):
    return packs.remove_item(name, body.get("type", ""), body.get("item_name", ""))


@app.post("/api/copy-to-project")
def copy_to_project(body: dict):
    """Copy a global item into a project's .claude/ directory."""
    project_path = body.get("project_path", "")
    item_type = _TYPE_MAP.get(body.get("type", ""), body.get("type", ""))
    item_name = body.get("name", "")

    if not project_path or not item_type or not item_name:
        return {"success": False, "message": "缺少参数"}

    all_items = scanner.scan_all()
    source = None
    for item in all_items:
        if item.type == item_type and item.name == item_name:
            source = item
            break
    if source is None:
        return {"success": False, "message": f"未找到: {item_type}/{item_name}"}

    import shutil
    dest_dir = Path(project_path) / ".claude"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if item_type == "skill":
            dest = dest_dir / "skills" / Path(source.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copytree(source.path, str(dest))
        elif item_type == "rule":
            # Rules have subdirectory structure
            rel = Path(source.path).name
            dest = dest_dir / "rules" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(source.path, str(dest))
        else:
            # agent, command, mcp — single files
            key = item_type + "s"
            dest = dest_dir / key / Path(source.path).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(source.path, str(dest))
        return {"success": True, "message": f"已复制 {item_name} 到项目"}
    except Exception as e:
        return {"success": False, "message": str(e)}


app.mount("/static", StaticFiles(directory="static"), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8900))
    print(f"Project Manager → http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
