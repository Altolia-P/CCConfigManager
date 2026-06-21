# CONTEXT.md — CCConfigManager 领域词汇表

## 配置管理

- **Config Item（配置项）**: `~/.claude/` 下的一个配置文件或目录。7 种类型：Skills、Agents、Commands、Rules、MCP、Tools、Hooks。
- **Source（来源）**: 配置项的来源标识。包括 ECC、Gstack、Superpowers、Claude Mem、Example、Standalone、Unknown。由五层检测确定（.source 文件 → 插件目录 → 安装状态 → git → 内容特征）。
- **Status（状态）**: `active`（active 目录中）或 `archived`（archive 目录中）。
- **Type（类型）**: 配置项分类 — skill、agent、command、rule、mcp、tool、hook、workflow。

## 项目与配置包

- **Project（项目）**: 一个包含自己的 `.claude/` 目录的 git 仓库。CCConfigManager 可以管理它的本地配置并同步到全局 `~/.claude/`。项目发现通过扫描 markdown 文件中的 token 匹配。
- **Pack（配置包）**: 一组配置项（skills、agents、commands、rules）的策展集合，可导出为 JSON 与他人分享。
- **Copy to project**: 将配置项从全局 `~/.claude/` 物理复制到项目本地的 `.claude/` 目录。

## 工作流

- **Workflow（工作流）**: 由节点和边组成的有向无环图（DAG），定义自动化任务执行。两种模式：`auto`（自动推进）和 `step`（每步确认）。
- **Node（节点）**: 工作流中的一个执行单元。三种类型：
  - **Agent Node**: 调用 Anthropic API 执行任务的节点。可配置 skills、MCP servers、tools、权限。
  - **Gate（门禁）**: 条件判断节点，控制流程分支。支持 manual（手动确认）、auto（Claude 判断）、expression（表达式求值）。
  - **Hook（钩子）**: 在节点进入/离开时执行的 shell 命令或子 agent 调用。
- **Edge（边）**: 节点间的连接，可设置条件（manual/auto）。
- **Permission（权限）**: 节点级别的工具允许/阻止列表。`allows` 是白名单，`blocks` 是黑名单（支持参数匹配如 `Write(*.env)`）。
- **Produces（产出）**: 节点声明应生成的文件列表，执行后检查是否存在。

## 执行引擎

- **Agent Runner**: 调用 Anthropic API 的客户端。合并 agent 定义 + skills + MCP 工具，管理 tool use 循环，支持超时和最大轮次限制。
- **MCP Client**: 通用 JSON-RPC 客户端，支持 stdio 子进程和 HTTP 两种传输方式。自动从 `mcp-servers.json` 发现工具。
- **Sandbox（沙箱）**: 限制 agent 的文件 I/O 只能访问项目目录，阻止 `.env`、`.git/`、`node_modules/` 等敏感路径。
- **Run（运行记录）**: 一次工作流执行的完整记录，包含每个节点的状态、输出、时间戳。持久化为 JSON 文件。
- **Topological Sort**: 工作流节点按拓扑顺序执行（Kahn 算法），保证依赖关系正确。
- **Run Lock**: 每个 workflow slug 同时只能有一个 run 在执行，防止重复触发。
