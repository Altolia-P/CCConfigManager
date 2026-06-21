import json
import os
import subprocess
from pathlib import Path


def _real(path: str | Path) -> str:
    """Resolve symlinks/junctions and normalize to canonical absolute path."""
    return os.path.realpath(str(path))


class SourceDetector:
    """Four-layer source detection: .source cache -> plugins -> install-state -> git -> standalone."""

    def __init__(self, claude_dir: str):
        self.claude_dir = _real(claude_dir)
        self._git_map: dict[str, str] = {}
        self._install_state_cache: dict[str, str] = {}  # {real_dest_path: source_name}
        self._install_state_loaded = False
        self._build_git_map()

    def _build_git_map(self) -> None:
        try:
            walk = os.walk(self.claude_dir)
        except FileNotFoundError:
            return  # ~/.claude/ doesn't exist yet — no git sources to detect
        for root, dirs, _ in walk:
            # Skip plugin repos — they are handled by layer 2
            try:
                rel = Path(root).relative_to(self.claude_dir)
            except ValueError:
                continue
            if "plugins" in rel.parts:
                continue
            if ".git" in dirs:
                repo_root = _real(root)
                name = self._git_repo_name(repo_root)
                if name:
                    self._git_map[repo_root] = name
                dirs.remove(".git")

    def _git_repo_name(self, repo_path: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path, capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                name = url.rstrip("/").split("/")[-1]
                return name.removesuffix(".git").lower()
        except Exception:
            pass
        return None

    def _load_install_state(self) -> None:
        if self._install_state_loaded:
            return
        claude_path = Path(self.claude_dir)
        if not claude_path.is_dir():
            self._install_state_loaded = True
            return
        for entry in claude_path.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            state_file = entry / "install-state.json"
            if not state_file.is_file():
                continue
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                source = entry.name.lower()
                for op in data.get("operations", []):
                    dest = op.get("destinationPath", "")
                    if dest:
                        self._install_state_cache[_real(dest)] = source
            except Exception:
                pass
        self._install_state_loaded = True

    def detect(self, item_path: str, item_type: str) -> str:
        item = _real(item_path)

        source = self._read_source(item, item_type)
        if source:
            return source

        source = self._detect_by_plugins(item)
        if source:
            self._write_source(item, item_type, source)
            return source

        source = self._detect_by_install_state(item)
        if source:
            self._write_source(item, item_type, source)
            return source

        source = self._detect_by_git(item)
        if source:
            self._write_source(item, item_type, source)
            return source

        source = self._detect_by_content(item, item_type)
        if source:
            self._write_source(item, item_type, source)
            return source

        self._write_source(item, item_type, "standalone")
        return "standalone"

    def _source_file_path(self, item: str, item_type: str) -> Path | None:
        ip = Path(item)
        if item_type == "skill":
            return ip / ".source"
        else:
            return ip.parent / f".{ip.stem}.source"

    def _read_source(self, item: str, item_type: str) -> str | None:
        sf = self._source_file_path(item, item_type)
        if sf and sf.is_file():
            content = sf.read_text(encoding="utf-8").strip()
            if content:
                return content
        return None

    def _write_source(self, item: str, item_type: str, source: str) -> None:
        sf = self._source_file_path(item, item_type)
        if sf:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text(source, encoding="utf-8")

    def _detect_by_plugins(self, item: str) -> str | None:
        plugins_file = Path(self.claude_dir) / "plugins" / "installed_plugins.json"
        if not plugins_file.is_file():
            return None
        try:
            data = json.loads(plugins_file.read_text(encoding="utf-8"))
            for plugin_id, instances in data.get("plugins", {}).items():
                source = plugin_id.split("@")[0].lower()
                for inst in instances:
                    install_path = _real(inst["installPath"])
                    if item.startswith(install_path):
                        return source
        except Exception:
            pass
        return None

    def _detect_by_install_state(self, item: str) -> str | None:
        self._load_install_state()
        # Check item path and archive-swapped variants
        candidates = [item]
        if "-archive" in item:
            candidates.append(item.replace("-archive", ""))
        else:
            # Also try if item was moved from archive to active
            parts = item.replace("\\", "/").split("/")
            for i, p in enumerate(parts):
                if p in ("skills", "agents", "commands", "rules"):
                    archive_variant = "/".join(parts[:i] + [p + "-archive"] + parts[i+1:])
                    candidates.append(archive_variant)
                    break

        for candidate in candidates:
            for dest_path, source in self._install_state_cache.items():
                if dest_path.startswith(candidate):
                    return source
        return None

    def _detect_by_git(self, item: str) -> str | None:
        for repo_root, source in self._git_map.items():
            if item.startswith(repo_root):
                return source
        return None

    def _collect_known_sources(self) -> set[str]:
        sources: set[str] = set()
        sources.update(self._git_map.values())
        sources.update(self._install_state_cache.values())
        plugins_file = Path(self.claude_dir) / "plugins" / "installed_plugins.json"
        if plugins_file.is_file():
            try:
                data = json.loads(plugins_file.read_text(encoding="utf-8"))
                for plugin_id in data.get("plugins", {}):
                    sources.add(plugin_id.split("@")[0].lower())
            except Exception:
                pass
        return {s for s in sources if s and len(s) > 1}

    def _detect_by_content(self, item: str, item_type: str) -> str | None:
        ip = Path(item)
        if item_type == "skill":
            md_path = ip / "SKILL.md"
        else:
            md_path = ip
        if not md_path.is_file():
            return None
        known = self._collect_known_sources()
        try:
            text = md_path.read_text(encoding="utf-8")
            for line in text.split("\n")[:30]:
                for word in line.split():
                    stripped = word.strip("().,:;\"'")
                    if stripped in known:
                        return stripped
        except Exception:
            pass
        return None
