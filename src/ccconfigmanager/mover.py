import shutil
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = ".claude/skills-manager.log"


class Mover:
    """Moves items between active and archived zones, writes operation log."""

    def __init__(self, claude_dir: str):
        self.claude_dir = Path(claude_dir).resolve()
        self._archive_map: dict[str, str] = {
            "skill": "skills-archive",
            "agent": "agents-archive",
            "command": "commands-archive",
            "rule": "rules-archive",
            "mcp": "mcp-configs",
            "tool": "mcp-configs",
            "workflow": "workflows",
        }
        self._active_map: dict[str, str] = {
            "skill": "skills",
            "agent": "agents",
            "command": "commands",
            "rule": "rules",
            "mcp": "mcp-configs",
            "tool": "mcp-configs",
            "workflow": "workflows",
        }

    def move(self, item_path: str, item_type: str, item_name: str, to_status: str) -> dict:
        """Move item to active or archived. Returns {success, message}."""
        src = Path(item_path)
        if not src.exists():
            return {"success": False, "message": f"路径不存在: {item_path}"}

        target_dir_name = (
            self._archive_map[item_type] if to_status == "archived"
            else self._active_map[item_type]
        )
        dest_dir = self.claude_dir / target_dir_name

        if item_type == "skill":
            dest = dest_dir / src.name
        elif item_type == "rule":
            # Rules use subdir/filename structure; preserve relative path
            try:
                src_rel = src.relative_to(self.claude_dir / "rules-archive" if "archive" in str(src) else self.claude_dir / "rules")
            except ValueError:
                src_rel = Path(src.name)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src_rel
        else:
            dest = dest_dir / src.name

        if dest.exists():
            return {"success": False, "message": f"目标已存在: {dest}"}

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

            # Also move .source file
            self._move_source(src, dest, item_type)

            from_status = "archived" if to_status == "active" else "active"
            self._log(item_type, item_name, from_status, to_status)

            return {"success": True, "message": f"已从 {from_status} 移至 {to_status}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _move_source(self, src: Path, dest: Path, item_type: str) -> None:
        if item_type == "skill":
            src_source = src / ".source"
        else:
            src_source = src.parent / f".{src.stem}.source"

        if src_source.is_file():
            if item_type == "skill":
                dest_source = dest / ".source"
            else:
                dest_source = dest.parent / f".{dest.stem}.source"
            try:
                shutil.move(str(src_source), str(dest_source))
            except Exception:
                pass

    def _log(self, item_type: str, name: str, from_status: str, to_status: str) -> None:
        log_file = Path.home() / LOG_PATH
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        entry = f"{ts} | MOVE | {item_type}s/{name} | {from_status} → {to_status}\n"
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def get_logs(self, limit: int = 50) -> list[str]:
        log_file = Path.home() / LOG_PATH
        if not log_file.is_file():
            return []
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        return lines[-limit:] if lines else []
