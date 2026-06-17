# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Web-based Claude Code config manager for `~/.claude/`. Browse, search, edit, move, and organize 7 config types: Skills, Agents, Commands, Rules, MCP, Tools, Workflows. Plus project-level config management and curated config packs.

## Commands

```bash
pip install -r requirements.txt
python -m ccconfigmanager  # → http://127.0.0.1:8900
PORT=9000 python -m ccconfigmanager  # override port
```

Windows: `setup.bat` → `start.bat`. macOS/Linux: `./setup.sh` → `./start.sh`.

## Architecture

```
src/ccconfigmanager/
├── __init__.py
├── __main__.py       # python -m ccconfigmanager
├── app.py            # FastAPI + CORS + all routes + static mount + main()
├── scanner.py        # Walk ~/.claude/ + plugins + projects, recursive rules
├── source_detector.py # Five-layer: .source → plugins → install-state → git → content
├── mover.py          # shutil.move() + .source sync + skills-manager.log
├── mcp_tools.py      # MCP tool discovery via JSON-RPC, cache to .tools-cache.json
├── projects.py       # Project CRUD in ~/.claude/project-manager/projects.json
├── packs.py          # Curated packs in ~/.claude/project-manager/packs.json
└── static/index.html # Single-file frontend — HTML + CSS + vanilla JS
```

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/types` | 7 types |
| `GET` | `/api/items?type=&source=&status=&search=` | Filtered list |
| `GET` | `/api/item/{type}/{name}` | Detail |
| `PUT` | `/api/item/{type}/{name}` | Edit content/description |
| `POST` | `/api/move` | Move active↔archive |
| `GET` | `/api/stats` | Counts per type |
| `GET` | `/api/logs` | Operation log |
| `POST` | `/api/mcp/refresh-tools` | Background MCP tool discovery |
| `GET` | `/api/projects` | List projects |
| `POST` | `/api/projects` | Create project |
| `DELETE` | `/api/projects/{name}` | Delete project |
| `POST` | `/api/projects/{name}/items` | Add item to project |
| `GET` | `/api/project-items?path=` | Scan project .claude/ |
| `POST` | `/api/copy-to-project` | Copy global item to project |
| `GET` | `/api/packs` | List packs |
| `POST` | `/api/packs` | Create pack |
| `DELETE` | `/api/packs/{name}` | Delete pack |
| `POST` | `/api/packs/{name}/items` | Add item to pack |

## Key constraints

- **No React/Vue/npm/webpack/TypeScript** — plain HTML/CSS/JS
- **No database** — filesystem is the data store
- **No authentication** — local single-user tool
- **Python files < 300 lines** each
- **No hardcoded paths** — use `os.path.expanduser("~")`
- **Port 8900** default, `PORT` env var
- **Source tags dynamic** — JS hash-based coloring, no hardcoded CSS per source
