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


def apply_to_project(pack_name: str, project_name: str) -> dict:
    """Write pack contents into a project's filesystem.

    - CLAUDE.md: insert/update a skill routing section
    - rules: copy .md files to <project>/.claude/rules/
    - commands: copy .md files to <project>/.claude/commands/
    """
    data = _load()
    pack = data.get("packs", {}).get(pack_name)
    if not pack:
        return {"success": False, "message": f"配置包 {pack_name} 不存在"}

    from . import projects as projects_data
    proj = projects_data.get(project_name)
    if not proj:
        return {"success": False, "message": f"项目 {project_name} 不存在"}

    proj_path = Path(proj.get("path", ""))
    if not proj_path.is_dir():
        return {"success": False, "message": f"项目路径已失效: {proj.get('path', '')}"}

    claude_dir = proj_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    details = {
        "claude_md": "skipped",
        "skills_listed": 0,
        "rules_copied": 0,
        "rules_skipped": 0,
        "commands_copied": 0,
        "commands_skipped": 0,
    }

    # --- 1. CLAUDE.md skill routing section ---
    skill_names = pack.get("skills", [])
    if skill_names:
        details["claude_md"], details["skills_listed"] = _write_claude_routes(
            claude_dir, pack_name, skill_names
        )

    # --- 2. Copy rules ---
    from .registry import CLAUDE_DIR
    global_rules = Path(CLAUDE_DIR) / "rules"
    proj_rules = claude_dir / "rules"
    for rule_name in pack.get("rules", []):
        src = global_rules / (rule_name + ".md")
        if not src.is_file():
            details["rules_skipped"] += 1
            continue
        dst = proj_rules / (rule_name + ".md")
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            details["rules_copied"] += 1
        except Exception:
            details["rules_skipped"] += 1

    # --- 3. Copy commands ---
    global_cmds = Path(CLAUDE_DIR) / "commands"
    proj_cmds = claude_dir / "commands"
    for cmd_name in pack.get("commands", []):
        src = global_cmds / (cmd_name + ".md")
        if not src.is_file():
            details["commands_skipped"] += 1
            continue
        dst = proj_cmds / (cmd_name + ".md")
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            details["commands_copied"] += 1
        except Exception:
            details["commands_skipped"] += 1

    parts = []
    if details["skills_listed"]:
        parts.append(f"{details['skills_listed']} 个 skill 路由")
    if details["rules_copied"]:
        parts.append(f"{details['rules_copied']} 个 rule")
    if details["commands_copied"]:
        parts.append(f"{details['commands_copied']} 个 command")
    skipped = details["rules_skipped"] + details["commands_skipped"]
    msg = "、".join(parts) if parts else "无变更"
    if skipped:
        msg += f"（跳过 {skipped} 个不存在的文件）"

    return {"success": True, "message": f"已应用「{pack_name}」到「{project_name}」: {msg}", "details": details}


def _write_claude_routes(claude_dir: Path, pack_name: str, skill_names: list[str]) -> tuple[str, int]:
    """Generate or update the skill routing section in CLAUDE.md. Returns (action, count)."""
    from .registry import scanner

    all_items = scanner.scan_all()
    skill_map: dict[str, str] = {}
    for item in all_items:
        if item.type == "skill" and item.name in skill_names:
            desc = item.description or ""
            if desc and desc != "无描述":
                first = desc.split("。")[0].split(". ")[0].strip()
                skill_map[item.name] = first[:80]
            else:
                skill_map[item.name] = ""

    if not skill_map:
        return "skipped", 0

    lines = [
        "<!-- CCConfigManager:ROUTES_START -->",
        f"# Skill 路由规则 (来自「{pack_name}」)",
        "",
        "遇到以下场景时，**必须**优先调用对应 Skill：",
        "",
    ]
    for name, desc in sorted(skill_map.items()):
        trigger = _get_trigger(name, desc)
        if trigger:
            lines.append(f"- **{trigger}** → 调用 `{name}`")
        elif desc:
            lines.append(f"- `{name}` — {desc}")
        else:
            lines.append(f"- `{name}`")
    lines.append("<!-- CCConfigManager:ROUTES_END -->")
    section = "\n".join(lines) + "\n"

    # CLAUDE.md lives at project root, not inside .claude/
    claude_md = claude_dir.parent / "CLAUDE.md"
    marker_start = "<!-- CCConfigManager:ROUTES_START -->"
    marker_end = "<!-- CCConfigManager:ROUTES_END -->"

    try:
        if claude_md.is_file():
            existing = claude_md.read_text(encoding="utf-8")
            if marker_start in existing and marker_end in existing:
                before = existing[:existing.index(marker_start)]
                after = existing[existing.index(marker_end) + len(marker_end):]
                new_content = before.rstrip("\n") + "\n\n" + section + "\n" + after.lstrip("\n")
                claude_md.write_text(new_content, encoding="utf-8")
                return "updated", len(skill_map)
            else:
                new_content = section + "\n" + existing
                claude_md.write_text(new_content, encoding="utf-8")
                return "updated", len(skill_map)
        else:
            claude_md.write_text(section + "\n", encoding="utf-8")
            return "created", len(skill_map)
    except Exception as e:
        return "skipped", 0


def _get_trigger(name: str, desc: str) -> str:
    """Extract a trigger phrase from skill description or curated mapping."""
    # Curated triggers for common skills
    TRIGGERS: dict[str, str] = {
        "teach-concept": "解释技术概念、讲解原理",
        "challenge-generator": "生成练习题、测验、挑战",
        "misconception-detector": "诊断概念误解、纠正错误模型",
        "lesson-plan": "创建学习路线图、课程规划",
        "find-your-level": "评估学习者当前水平",
        "revision-mode": "结构化复习、间隔重复",
        "spaced-repetition": "结构化复习、间隔重复",
        "debug-teacher": "引导式调试、假设驱动排错",
        "deep-dive": "深入理解机制、权衡、边界",
        "simplify-topic": "类比优先、降低抽象层次教学",
        "socratic-mode": "苏格拉底式提问教学",
        "flashcards": "主动回忆闪卡、间隔记忆",
        "project-review": "评估项目、代码质量评审",
        "interview-mode": "模拟技术面试、压力测试",
        "weak-area-tracker": "记录学习弱点、跟踪进步",
        "repo-understand": "仓库学习、代码库导读",
        "build-with-me": "引导真实项目实现、边做边学",
        "check-understanding": "验证概念理解、检测薄弱环节",
        "learning-memory": "维护学习者档案、跨会话记忆",
        "continuous-learning": "会话结束后自动提取模式",
        "continuous-learning-v2": "基于本能的学习系统、自动模式提取",
        "scrape": "网页数据提取、爬取内容",
        "ship": "部署发布、PR 创建、代码推送",
        "strategic-compact": "上下文压缩策略、会话管理",
        "skill-create": "分析仓库提取编码模式、生成 SKILL.md",
        "anysearch": "实时搜索、网页查询",
        "documentation-lookup": "查阅框架/库文档、API 参考",
        "find-skills": "发现、安装 agent skills",
        "iterative-retrieval": "逐步优化上下文检索",
    }
    if name in TRIGGERS:
        return TRIGGERS[name]

    # Extract from description: look for "Use when asked to ..." / "触发词: ..."
    import re
    m = re.search(r'Use when asked to\s*["“](.+?)["”]', desc, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'触发[词词].*?[:：]\s*(.+?)(?:[。\n]|$)', desc)
    if m:
        return m.group(1).strip()
    return ""


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
