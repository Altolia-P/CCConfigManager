# Claude Code Project Manager

Web 界面的 Claude Code 配置管理工具。浏览、搜索、编辑、组织 `~/.claude/` 下的 Skills、Agents、Commands、Rules、MCP、Tools、Workflows。

![](https://img.shields.io/badge/python-3.10+-blue)
![](https://img.shields.io/badge/license-MIT-green)

## 快速开始

### Windows
```
双击 setup.bat → 安装完成 → 双击 start.bat → 浏览器自动打开
```

### macOS / Linux
```bash
chmod +x setup.sh && ./setup.sh
./start.sh
```

### 手动启动
```bash
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:8900
```

端口可改：`PORT=9000 python app.py`

## 功能

| 类型 | 浏览 | 搜索 | 编辑 | 搬家 |
|------|------|------|------|------|
| Skills (190+) | ✓ | ✓ | ✓ 内容 | ✓ 活跃↔隔离 |
| Agents (49) | ✓ | ✓ | ✓ 内容 | ✓ |
| Commands (83) | ✓ | ✓ | ✓ 内容 | ✓ |
| Rules (87) | ✓ | ✓ | ✓ 内容 | ✓ |
| MCP (27) | ✓ | ✓ | ✓ 描述 | - |
| Tools (101+) | ✓ | ✓ | - | - |
| Workflows (14) | ✓ | ✓ | ✓ JSON | - |

额外功能：
- **来源自动检测** — ECC / Gstack / Superpowers / 插件 / 手动，新来源自动适配配色
- **项目管理** — 关联项目路径，自动扫 `.claude/` 配置，全局项一键复制到项目
- **配置包** — 收藏常用配置打包归类
- **MCP Tool 发现** — 后台连接 MCP server 自动发现 tools 并缓存
- **Workflow 编辑** — Auto/Step 模式分开展示，可视编辑 JSON

## 项目结构

```
project-manager/
├── app.py              # FastAPI 入口
├── scanner.py          # 目录扫描
├── source_detector.py  # 五层来源检测
├── mover.py            # 搬家 + 日志
├── mcp_tools.py        # MCP tool 发现
├── projects.py         # 项目管理
├── packs.py            # 配置包管理
├── static/
│   └── index.html      # 前端（单文件，零构建）
├── requirements.txt
├── setup.bat / setup.sh
└── docs/               # 设计文档
```

## 文档

- [PRD](docs/PRD.md) — 产品定义
- [架构](docs/ARCHITECTURE.md) — 技术选型
- [数据模型](docs/DATA-MODEL.md) — 来源检测流程
- [UI 规格](docs/UI-SPEC.md) — 界面布局
- [实现计划](docs/IMPLEMENTATION-PLAN.md) — 分阶段步骤

## 技术栈

Python 3 + FastAPI + uvicorn，前端单文件 HTML + 原生 JS + CSS，零 npm / 零构建工具。

## License

MIT
