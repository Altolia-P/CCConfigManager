# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Web-based Claude Code config manager for `~/.claude/`. Browse, search, edit, move, and organize 7 config types: Skills, Agents, Commands, Rules, MCP, Tools, Workflows. Plus project-level config management, curated config packs, and a visual workflow editor with SVG canvas.

## Stack

- **Frontend**: TypeScript + Vite (vanilla TS, no React/Vue), plain CSS, HTML
- **Backend**: Python FastAPI on port 8900 (serves API + static assets)
- **Dev server**: Vite on port 8920, proxies `/api` and `/static` to `http://127.0.0.1:8900`

## Commands

```bash
# Start Python backend
python -m ccconfigmanager                # port 8900
PORT=9000 python -m ccconfigmanager     # override port

# TypeScript dev server (hot reload on :8920, proxies API to :8900)
npm run dev

# TypeScript type-check only (no emit)
npm run typecheck

# Build frontend for production
npm run build                            # outputs to src/ccconfigmanager/static/dist/
```

**One-click start:** `start.bat` (Windows) or `./start.sh` (macOS/Linux) — auto-installs everything on first run.
**Dev:** run backend + `npm run dev` in separate terminals, or use `dev.bat` (Windows).

## Architecture

### Frontend (`src/` — TypeScript)

```
src/
├── main.ts              # Entry — search, keyboard shortcuts (Ctrl+K), boot sequence
├── types.ts             # All type definitions: ConfigItem, AppState, WorkflowData, etc.
├── state.ts             # Global mutable state object + constants (TYPES, WORKFLOW_MODES, SOURCES)
├── api.ts               # All fetch() calls to Python backend — items, projects, packs, workflows, import
├── utils.ts             # DOM helpers ($, $$), escape functions, fetchJSON, source tag coloring, toast
├── ui/
│   ├── sidebar.ts       # Left sidebar: type nav, source/status filters, project/pack lists, import
│   ├── items.ts         # Center list panel + right detail panel, selection, save/edit/move
│   ├── projects.ts      # Project CRUD, auto-discovery, project items view
│   └── packs.ts         # Pack CRUD, pack items view, export
├── workflow/
│   ├── engine.ts        # Core WF engine — node/edge CRUD, undo/redo (50-deep stack), zoom/pan, SVG DOM
│   ├── renderer.ts      # SVG node/edge rendering — agent nodes (200×64), gate diamonds, hook pills
│   ├── interaction.ts   # Mouse/keyboard/wheel handlers — drag, draw edges, pan, zoom
│   ├── properties.ts    # Property overlay — node/edge/workflow editing, permissions editor
│   └── integration.ts   # Glue between WF engine and main app — save, export, fullscreen, V1→V2 conversion
└── css/
    ├── main.css         # Layout, sidebar, list panel, detail panel, source tags, toast
    └── workflow.css     # Workflow editor: toolbar, sidebar, canvas, node/edge styles, overlay
```

### Key patterns

- **Global state** (`state.ts`): single `state: AppState` object mutated by all modules. No reactivity framework — imperative DOM updates after state changes.
- **Lazy imports**: sidebar and integration use dynamic `import()` to avoid circular dependencies at module parse time.
- **Workflow engine** (`engine.ts`): all methods on a singleton `WF` object exposed to `window.WF` for inline `onclick` handlers. Undo/redo via JSON snapshots on a ring buffer.
- **Source tags**: hash-based color assignment from a 12-color palette (`utils.ts:sourceStyle`) — no hardcoded per-source CSS.
- **No router**: the SPA uses state flags (`state.type`, `state.project`, `state.pack`, `state.wfMode`) to determine which view renders.

### Backend (`src/ccconfigmanager/` — Python)

```text
src/ccconfigmanager/
├── __init__.py
├── __main__.py            # python -m ccconfigmanager
├── app.py                 # FastAPI + CORS + route registration + static mount + main()  (~40 lines)
├── registry.py            # Shared singletons: scanner, detector, mover, TYPE_MAP, ALL_TYPES
├── routes/
│   ├── __init__.py
│   ├── items.py           # Core CRUD: index, types, items list/detail/batch, move, stats, logs
│   ├── proj.py            # Project CRUD, discover, sync, copy-to-project
│   ├── packs.py           # Pack CRUD + export
│   ├── workflows.py       # Workflow CRUD, create/copy/delete, migrate, export/import
│   ├── runs.py            # Workflow execute, run status, approve/retry/cancel, validate
│   └── agents.py          # Per-agent model/API key/base_url config
├── scanner.py             # Walk ~/.claude/ + plugins + projects, recursive rules
├── source_detector.py     # Five-layer: .source → plugins → install-state → git → content
├── mover.py               # shutil.move() + .source sync + skills-manager.log
├── mcp_tools.py           # MCP tool discovery via JSON-RPC, cache to .tools-cache.json
├── projects.py            # Project data layer — CRUD in ~/.claude/CCConfigManager/projects.json
├── packs.py               # Pack data layer — CRUD in ~/.claude/CCConfigManager/packs.json
├── executor/
│   ├── __init__.py
│   ├── engine.py           # Workflow orchestration — node execution, gate/hook/produces, retry, parallel-lock
│   ├── agent_runner.py     # Anthropic API agent call — tool use loop, MCP integration, timeout, permissions
│   ├── mcp_client.py       # Generic MCP JSON-RPC client — McpClient + McpManager for any stdio MCP server
│   ├── tools.py            # 13 built-in tool handlers — Read/Write/Edit/Bash/Grep/Glob/WebFetch/WebSearch/...
│   ├── permissions.py      # Tool allow/block filtering
│   ├── hooks.py            # Shell + agent hooks at onEnter/onLeave with node context passthrough
│   ├── gate.py             # Auto/manual/expression gate conditions
│   ├── produces.py         # File existence check after agent execution
│   ├── sandbox.py          # Path resolution + blocked-pattern sandbox
│   ├── run_store.py        # JSON-based run state persistence
│   └── workflow_loader.py  # Topological sort (Kahn's algorithm) + JSON→dict loading
└── static/                # Legacy frontend + Vite build output
```

## API endpoints

Same as previous version — all endpoints unchanged. The TypeScript frontend calls the same Python API. See `api.ts` for the client-side fetch wrappers.

## Key constraints

- **No React/Vue framework** — vanilla TypeScript with imperative DOM updates
- **No database** — filesystem is the data store
- **No authentication** — local single-user tool
- **No hardcoded paths** — use `os.path.expanduser("~")` in Python
- **Python files < 300 lines** each
- **Port 8900** default for Python, **8920** for Vite dev server
- **Source tags dynamic** — hash-based coloring in JS, no hardcoded CSS per source
