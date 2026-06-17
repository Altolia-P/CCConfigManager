# CCConfigManager

Web 界面的 Claude Code 配置管理工具。一站式管理 `~/.claude/` 下的所有配置类型。

```
┌──────────────────────────────────────────────────┐
│  🔍 搜索...                          Ctrl+K 搜索  │
├────────────┬──────────────────┬──────────────────┤
│ ▸ Skills   │ ● investigate   │  名称: investigate│
│   🟢 138   │   gstack        │  类型: skill      │
│   🔴 52    │   系统调试...    │  路径: ~/.claude/ │
│ ▸ Agents   │ ● code-reviewer │                   │
│   49       │   ecc           │  ┌──────────────┐ │
│ ▸ Commands │   代码审查...   │  │ SKILL.md 内容 │ │
│ ▸ Rules    │ ● ...           │  │ (可编辑保存)  │ │
│ ▸ MCP (27) │                 │  └──────────────┘ │
│ ▸ Tools    │                 │ [保存] [搬家]    │
│ ▸Workflows │                 │ [加到项目][加包] │
│   Auto/Step│                 │                  │
│ ══ 项目 ══ │                 │                  │
│ ▸ 我的项目 │                 │                  │
│ ══ 配置包 ═│                 │                  │
│ ▸ 前端工具 │                 │                  │
├────────────┴──────────────────┴──────────────────┤
│  共 400+ 项 · 活跃 300 · 隔离 100               │
└──────────────────────────────────────────────────┘
```

## 安装

### Windows

下载解压后双击 `setup.bat`，自动创建虚拟环境、安装依赖、生成启动脚本。之后双击 `start.bat` 启动。

### macOS / Linux

```bash
chmod +x setup.sh && ./setup.sh
./start.sh
```

### pip 安装

```bash
pip install -r requirements.txt
python app.py
# 浏览器打开 http://127.0.0.1:8900
```

端口可改：`PORT=9000 python app.py`

## 功能

### 7 种配置类型

| 类型 | 数量 | 支持操作 |
|------|------|----------|
| Skills | 190+ | 浏览、搜索、编辑内容、搬家、加项目/包 |
| Agents | 49 | 同上 |
| Commands | 83 | 同上 |
| Rules | 87 | 同上 |
| MCP | 27 | 浏览、搜索、编辑描述 |
| Tools | 101+ | 浏览（从 MCP server 自动发现） |
| Workflows | 14 | 浏览、编辑 JSON、Auto/Step 分开展示 |

### 来源自动检测

新下载的配置自动识别来源（ECC / Gstack / Superpowers / 插件 / 手动），不同颜色标签区分。来源名通过哈希自动配色，任何新来源都不需要改代码。

### 搬家

活跃区 ↔ 隔离区一键移动，带确认对话框，操作日志写入 `~/.claude/skills-manager.log`。

### 编辑

点击任意配置 → 右侧显示内容 → 直接编辑 → Ctrl+S 或点保存 → 写回源文件。

### 项目管理

创建项目并关联本地路径，自动扫描该路径下 `.claude/` 的配置。全局配置可一键复制到项目，提高项目内技能触发率。

### 配置包

创建命名包（如"前端工具集"、"Python 开发"），把常用配置打包收藏。

### MCP Tool 发现

后台连接所有 MCP server，通过 JSON-RPC 协议自动发现 tools 并缓存。点击侧边栏刷新按钮可手动更新。

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` | 聚焦搜索框 |
| `Esc` | 清除搜索 |
| `Ctrl+S` | 保存编辑内容 |

## 技术栈

- **后端**: Python 3.10+ / FastAPI / uvicorn
- **前端**: 单文件 HTML + 原生 JS + CSS，零 npm / 零构建
- **存储**: 文件系统，无数据库

## 项目结构

```
├── app.py              # FastAPI 入口
├── scanner.py          # 目录扫描
├── source_detector.py  # 五层来源检测
├── mover.py            # 搬家 + 日志
├── mcp_tools.py        # MCP tool 发现
├── projects.py         # 项目管理
├── packs.py            # 配置包管理
├── static/index.html   # 前端
├── setup.bat / setup.sh
├── requirements.txt
└── docs/               # 设计文档
```

## License

MIT
