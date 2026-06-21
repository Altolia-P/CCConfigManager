# CCConfigManager

Web 界面的 Claude Code 配置管理工具。一站式管理 `~/.claude/` 下的 Skills、Agents、Commands、Rules、MCP、Tools、Workflows。

```
┌──────────────────────────────────────────────────┐
│  🔍 搜索...                          Ctrl+K 搜索  │
├────────────┬──────────────────┬──────────────────┤
│ ▸ Skills   │ ● skill-name     │  名称: ...       │
│ ▸ Agents   │   source-tag     │  类型: skill     │
│ ▸ Commands │   描述文字...    │  路径: ~/.claude/ │
│ ▸ Rules    │ ● ...           │                   │
│ ▸ MCP      │                 │  ┌──────────────┐ │
│ ▸ Tools    │                 │  │ 配置内容预览 │ │
│ ▸Workflows │                 │  │ (可编辑保存)  │ │
│   Auto/Step│                 │  └──────────────┘ │
│ ══ 项目 ══ │                 │ [保存] [搬家]    │
│ ══ 配置包 ═│                 │ [加到项目][加包] │
├────────────┴──────────────────┴──────────────────┤
│  共 N 项 · 活跃 X · 隔离 Y                       │
└──────────────────────────────────────────────────┘
```

## 前提条件

- **Python 3.10+**（`python --version`）
- **Node.js 18+**（`node --version`）— 前端 TypeScript 编译需要
- **ANTHROPIC_API_KEY**（可选，仅工作流执行功能需要）

## 安装

### Windows

下载解压后，**双击 `start.bat`**。首次运行会自动完成安装（约 30 秒），之后秒启动。

### macOS / Linux

```bash
chmod +x start.sh && ./start.sh
```

同样首次自动安装，之后直接启动。

### 手动安装

```bash
# 1. Python 环境
python -m venv venv && source venv/bin/activate
pip install -e .

# 2. 前端构建
npm install && npm run build

# 3. 启动
python -m ccconfigmanager
```

端口可改：`PORT=9000 python -m ccconfigmanager`

### 开发模式

```bash
# 终端1：后端
python -m ccconfigmanager --reload

# 终端2：前端（热重载，端口 8920）
npm run dev
```

## 功能

### 7 种配置类型

| 类型 | 支持操作 |
|------|----------|
| Skills | 浏览、搜索、编辑内容、搬家、加项目/包 |
| Agents | 同上 |
| Commands | 同上 |
| Rules | 同上 |
| MCP | 浏览、搜索、编辑描述 |
| Tools | 浏览（从 MCP server 自动发现） |
| Workflows | 浏览、编辑 JSON、Auto/Step 分开展示 |

### 来源自动检测

配置自动识别来源（ECC / Gstack / Superpowers / 插件 / 手动），不同颜色标签区分。新来源通过哈希自动配色，无需改代码。

### 搬家

活跃区 ↔ 隔离区一键移动，带确认对话框，操作日志记录。

### 编辑

点击配置 → 右侧显示内容 → 直接编辑 → Ctrl+S 保存 → 写回源文件。

### 项目管理

创建项目关联本地路径，自动扫描 `.claude/` 配置。全局配置可一键复制到项目。

### 配置包

创建命名包（如"前端工具集"），常用配置打包收藏。

### MCP Tool 发现

后台连接 MCP server，JSON-RPC 协议自动发现 tools 并缓存。

### 数据存储

所有运行时数据存储在 `~/.claude/CCConfigManager/` 下：
- `projects.json` / `packs.json` — 项目和配置包
- `agent-config.json` — 各 Agent 的模型/API 配置
- `runs/` — 工作流执行记录
- `agent-tasks.jsonl` / `notifications.jsonl` — 工作流任务和通知

首次扫描会在每个配置目录写入 `.source` 标记文件以加速后续扫描。

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` | 聚焦搜索框 |
| `Esc` | 清除搜索 |
| `Ctrl+S` | 保存编辑 |

## 技术栈

- **后端**: Python 3.10+ / FastAPI / uvicorn
- **前端**: 单文件 HTML + 原生 JS + CSS，零构建工具
- **存储**: 文件系统，无数据库

## 项目结构

```
src/ccconfigmanager/   ← 源码
├── app.py             # FastAPI 入口 + 全部路由
├── scanner.py         # 目录扫描
├── source_detector.py # 五层来源检测
├── mover.py           # 搬家 + 日志
├── mcp_tools.py       # MCP tool 发现
├── projects.py        # 项目管理
├── packs.py           # 配置包
└── static/index.html  # 前端
```

## License

MIT
