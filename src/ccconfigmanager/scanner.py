import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import mcp_tools
from .source_detector import SourceDetector

SCAN_CACHE_TTL = 3.0  # seconds

@dataclass
class Item:
    type: str      # "skill" | "agent" | "command" | "rule"
    name: str
    source: str
    status: str    # "active" | "archived"
    path: str      # primary absolute path
    paths: list[str] = field(default_factory=list)
    description: str = ""
    content_preview: str = ""
    raw_content: str = ""


class Scanner:
    def __init__(self, claude_dir: str, detector: SourceDetector):
        self.claude_dir = Path(claude_dir).resolve()
        self.detector = detector
        self._scan_cache: list[Item] | None = None
        self._scan_cache_time: float = 0

    def scan_all(self) -> list[Item]:
        now = time.time()
        if self._scan_cache is not None and (now - self._scan_cache_time) < SCAN_CACHE_TTL:
            return self._scan_cache
        items: dict[tuple[str, str, str], Item] = {}

        self._scan_skill_dir("skills", "active", items, primary=True)
        self._scan_skill_dir("skills-archive", "archived", items, primary=True)
        self._scan_file_dir("agents", "agent", "active", items, primary=True)
        self._scan_file_dir("agents-archive", "agent", "archived", items, primary=True)
        self._scan_file_dir("commands", "command", "active", items, primary=True)
        self._scan_file_dir("commands-archive", "command", "archived", items, primary=True)
        self._scan_rules_dir("rules", "active", items, primary=True)
        self._scan_rules_dir("rules-archive", "archived", items, primary=True)
        self._scan_mcp(items)
        self._scan_tools(items)
        self._scan_workflows(items)
        self._scan_hooks(items)

        self._scan_plugins(items)

        result = sorted(items.values(), key=lambda i: (i.type, i.name))
        self._scan_cache = result
        self._scan_cache_time = now
        return result

    def invalidate_cache(self) -> None:
        self._scan_cache = None

    def scan_project(self, project_path: str) -> list[Item]:
        """Scan a project directory's .claude/ for config items."""
        base = (Path(project_path) / ".claude").resolve()
        if not base.is_dir():
            return []
        items: dict[tuple[str, str, str], Item] = {}
        self._scan_skill_dir(str(base / "skills"), "active", items, primary=True)
        self._scan_skill_dir(str(base / "skills-archive"), "archived", items, primary=True)
        self._scan_file_dir(str(base / "agents"), "agent", "active", items, primary=True)
        self._scan_file_dir(str(base / "agents-archive"), "agent", "archived", items, primary=True)
        self._scan_file_dir(str(base / "commands"), "command", "active", items, primary=True)
        self._scan_file_dir(str(base / "commands-archive"), "command", "archived", items, primary=True)
        self._scan_rules_dir(str(base / "rules"), "active", items, primary=True)
        self._scan_rules_dir(str(base / "rules-archive"), "archived", items, primary=True)
        return sorted(items.values(), key=lambda i: (i.type, i.name))

    def _add_item(self, items: dict, key: tuple[str, str, str], item: Item, primary: bool) -> None:
        if key in items:
            existing = items[key]
            if primary:
                item.paths = [item.path] + existing.paths
                items[key] = item
            else:
                existing.paths.append(item.path)
        else:
            items[key] = item
            item.paths = [item.path]

    def _scan_skill_dir(self, rel_dir: str, status: str, items: dict, primary: bool) -> None:
        base = self.claude_dir / rel_dir
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            source = self.detector.detect(str(entry), "skill")
            desc, preview = self._extract_description(skill_md)
            item = Item(
                type="skill", name=entry.name, source=source,
                status=status, path=str(entry),
                description=desc, content_preview=preview,
            )
            self._add_item(items, ("skill", entry.name, status), item, primary)

    def _scan_file_dir(self, rel_dir: str, item_type: str, status: str, items: dict, primary: bool) -> None:
        base = self.claude_dir / rel_dir
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if entry.name.startswith(".") or not entry.is_file():
                continue
            if entry.suffix != ".md":
                continue
            name = entry.stem
            source = self.detector.detect(str(entry), item_type)
            desc, preview = self._extract_description(entry)
            item = Item(
                type=item_type, name=name, source=source,
                status=status, path=str(entry),
                description=desc, content_preview=preview,
            )
            self._add_item(items, (item_type, name, status), item, primary)

    def _scan_rules_dir(self, rel_dir: str, status: str, items: dict, primary: bool) -> None:
        base = self.claude_dir / rel_dir
        if not base.is_dir():
            return
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
            rel_root = Path(root).relative_to(base)
            for fname in sorted(files):
                if fname.startswith(".") or not fname.endswith(".md"):
                    continue
                file_path = Path(root) / fname
                name = str(rel_root / Path(fname).stem) if str(rel_root) != "." else Path(fname).stem
                name = name.replace("\\", "/")
                source = self.detector.detect(str(file_path), "rule")
                desc, preview = self._extract_description(file_path)
                item = Item(
                    type="rule", name=name, source=source,
                    status=status, path=str(file_path),
                    description=desc, content_preview=preview,
                )
                self._add_item(items, ("rule", name, status), item, primary)

    def _scan_plugins(self, items: dict) -> None:
        plugins_file = self.claude_dir / "plugins" / "installed_plugins.json"
        if not plugins_file.is_file():
            return
        try:
            data = json.loads(plugins_file.read_text(encoding="utf-8"))
        except Exception:
            return
        for plugin_id, instances in data.get("plugins", {}).items():
            for inst in instances:
                install_path = Path(inst["installPath"]).resolve()
                if not install_path.is_dir():
                    continue
                self._scan_skill_dir(str(install_path / "skills"), "active", items, primary=False)
                self._scan_file_dir(str(install_path / "agents"), "agent", "active", items, primary=False)
                self._scan_file_dir(str(install_path / "commands"), "command", "active", items, primary=False)
                self._scan_rules_dir(str(install_path / "rules"), "active", items, primary=False)

    def _scan_mcp(self, items: dict) -> None:
        mcp_file = self.claude_dir / "mcp-configs" / "mcp-servers.json"
        if not mcp_file.is_file():
            return
        try:
            data = json.loads(mcp_file.read_text(encoding="utf-8"))
        except Exception:
            return
        for name, cfg in data.get("mcpServers", {}).items():
            if not isinstance(cfg, dict):
                continue
            desc = cfg.get("description", "")
            # Build a content preview showing the config
            preview_parts = []
            if cfg.get("command"):
                preview_parts.append(f"command: {cfg['command']} {' '.join(cfg.get('args',[]))}")
            if cfg.get("type"):
                preview_parts.append(f"type: {cfg['type']} (URL: {cfg.get('url','')})")
            if cfg.get("env"):
                env_keys = list(cfg["env"].keys())
                preview_parts.append(f"env: {', '.join(env_keys)}")
            item = Item(
                type="mcp", name=name, source="standalone",
                status="active", path=str(mcp_file),
                description=desc or f"MCP Server: {name}",
                content_preview="\n".join(preview_parts) or "MCP server configuration",
            )
            self._add_item(items, ("mcp", name, item.status), item, primary=True)

    def _scan_workflows(self, items: dict) -> None:
        wf_dir = self.claude_dir / "workflows"
        if not wf_dir.is_dir():
            return
        for entry in sorted(wf_dir.iterdir()):
            if not entry.is_file() or entry.suffix != ".json":
                continue
            try:
                raw = entry.read_text(encoding="utf-8")
                data = json.loads(raw)
            except Exception:
                continue
            name = data.get("slug", entry.stem)
            desc = data.get("description", "")
            mode = data.get("mode", "auto")
            preview_lines = [f"触发模式: {'阶段门禁 (Step)' if mode == 'step' else '自动编排 (Auto)'}"]
            # v1 format
            if "steps" in data:
                for s in data["steps"]:
                    preview_lines.append(f"  [{s.get('id','?')}] {s.get('label','')} → {s.get('agentSlug','')}")
            if "phases" in data:
                for p in data["phases"]:
                    preview_lines.append(f"  [{p.get('name','?')}] {p.get('description','')[:60]}")
            # v2 format (nodes+edges)
            if "nodes" in data:
                fmt_ver = "v2"
                node_count = len(data["nodes"])
                edge_count = len(data.get("edges", []))
                preview_lines.append(f"  节点: {node_count} · 连线: {edge_count}")
                for n in data["nodes"][:6]:
                    node_info = f"  [{n.get('type','?')}] {n.get('label','?')}"
                    if n.get('agentId'):
                        node_info += f" → {n['agentId']}"
                    preview_lines.append(node_info)
                if node_count > 6:
                    preview_lines.append(f"  ... 还有 {node_count - 6} 个节点")
            source = mode  # "auto" or "step" — colored differently
            item = Item(
                type="workflow", name=name, source=source,
                status="active", path=str(entry),
                description=desc, content_preview="\n".join(preview_lines),
                raw_content=raw,
            )
            self._add_item(items, ("workflow", name, item.status), item, primary=True)

    def _scan_hooks(self, items: dict) -> None:
        hooks_file = self.claude_dir / "hooks" / "hooks.json"
        if not hooks_file.is_file():
            return
        try:
            data = json.loads(hooks_file.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        for event, entries in data.get("hooks", {}).items():
            for idx, entry in enumerate(entries):
                matcher = entry.get("matcher", "*")
                name = f"{event}/{matcher}-{idx}"
                hook_list = entry.get("hooks", [])
                desc_parts = []
                for h in hook_list:
                    cmd = h.get("command", "")
                    if isinstance(cmd, list):
                        cmd_str = " ".join(cmd)
                    else:
                        cmd_str = str(cmd)
                    desc_parts.append(cmd_str[:80])
                desc = "; ".join(desc_parts) or f"Hook: {event} → {matcher}"
                preview = json.dumps(entry, indent=2, ensure_ascii=False)
                item = Item(
                    type="hook", name=name, source="standalone",
                    status="active", path=str(hooks_file),
                    description=desc, content_preview=preview,
                    raw_content=preview,
                )
                self._add_item(items, ("hook", name, item.status), item, primary=True)

    def _scan_tools(self, items: dict) -> None:
        cache = mcp_tools.load_cache(str(self.claude_dir))
        for server_name, tools in cache.items():
            for tool in tools:
                name = f"{server_name}/{tool['name']}"
                item = Item(
                    type="tool", name=name, source="mcp",
                    status="active", path=str(self.claude_dir / "mcp-configs" / "mcp-servers.json"),
                    description=tool.get("description", ""),
                    content_preview=f"Server: {server_name}\nTool: {tool['name']}\n{tool.get('description','')}",
                )
                self._add_item(items, ("tool", name, item.status), item, primary=True)

    def _extract_description(self, md_path: Path) -> tuple[str, str]:
        try:
            content = md_path.read_text(encoding="utf-8")
            lines = content.split("\n")[:20]
            preview = content[:2000]
        except Exception:
            return "无描述", ""

        in_frontmatter = False
        fm_dashes = 0
        for line in lines:
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
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("<!--") or stripped.startswith("<") or stripped.startswith("```") or stripped.startswith(">"):
                continue
            return stripped, preview

        return "无描述", preview
