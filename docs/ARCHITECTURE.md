# ARCHITECTURE — 技术架构

## 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Python 3 + FastAPI | AI 写 Python 质量最高，FastAPI 轻量够用 |
| 前端 | 单文件 HTML + 原生 JS + CSS | 零构建工具，改完刷新即看 |
| UI 框架 | 无 | CSS Grid + Flexbox 足够 |
| 前端依赖 | 无 | 不引入 npm/react/vue |
| 后端依赖 | fastapi, uvicorn | 最小依赖 |
| 模板引擎 | 无 | 前端纯静态，后端只提供 JSON API |

## 后端 API 设计

```
GET  /api/types                          → ["skills", "agents", "commands", "rules"]
GET  /api/items?type=skills&source=ecc   → [{name, source, description, status, path}, ...]
GET  /api/item/skills/investigate        → {name, source, description, status, path, content_preview}
POST /api/move                           → {type, name, to: "active"|"archived"} → {success, message}
GET  /api/stats                          → {skills: {active: 107, archived: 19}, agents: {active: 49}, ...}
GET  /api/logs?limit=50                  → [日志行, ...]
```

## 文件结构

```
project-manager/
├── app.py              # FastAPI 入口，路由注册，启动
├── scanner.py          # 扫描 ~/.claude/ 目录树，构建 item 列表
├── source_detector.py  # 四层来源检测（.source缓存→插件→安装清单→git→兜底）
├── mover.py            # 移动操作 + 日志写入
├── static/
│   └── index.html      # 全部前端（HTML + CSS + JS 单文件）
├── requirements.txt    # fastapi, uvicorn
└── README.md
```

## 关键决策

### 数据刷新：启动时全扫，不缓存
每次启动扫描所有目录，构建内存数据结构。不存磁盘缓存，不引入缓存失效问题。
扫描 200 个目录读 SKILL.md 前 20 行，约 1-2 秒。

### 来源识别：三层检测 + .source 缓存

首次扫描运行三层检测：
1. 插件系统：读 `installed_plugins.json`，路径匹配 installPath
2. 安装清单：扫描 `~/.claude/*/install-state.json`，查 destinationPath 表
3. Git 仓库：`git rev-parse` + `git remote get-url origin`，提取仓库名
4. 兜底：标记为 `standalone`

检测完成后写 `.source` 文件，后续扫描 O(1) 读取，不重复检测。
详见 `DATA-MODEL.md` 来源识别章节。

### 搬家操作：物理移动 + 日志
`shutil.move()` 直接移动文件/目录。
移动前有确认 API（前端负责确认对话框）。
每次移动追加一行到 `~/.claude/skills-manager.log`，格式：
`2026-06-16T12:00:00 | MOVE | skills/code-reviewer | active → archived`

### 前端：单文件，零构建
一个 `index.html` 包含所有 HTML、CSS、JS。
与后端通过 fetch API 通信。
不需要 webpack/vite/esbuild。

### 扩展预留
- API 返回的 item 对象包含 `type` 字段，添加新类型（如 mcp_servers）只需新增扫描逻辑
- 前端分类树由 API 返回的动态列表渲染，不硬编码类型
- CSS 使用变量，暗色模式只需换变量值
- 日志文件预留 `action` 字段，未来可加 `IMPORT`、`DELETE` 等操作
