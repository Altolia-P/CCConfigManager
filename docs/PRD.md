# PRD — Claude Code 配置管理工具

## 核心问题

用户有 200+ 个 Claude Code 配置项（Skills/Agents/Commands/Rules），分布在 `~/.claude/` 下的多个目录中。现有桌面工具（AgentSkills、claude-code-session-manager）无法完整扫描，也不支持自定义目录结构。

## 目标用户

只有一个用户：深度使用 Claude Code、安装了 ECC + Gstack + Superpowers 全家桶的开发者。

## 核心功能（v1）

### 1. 浏览
- 按类型切换：Skills / Agents / Commands / Rules
- Skills/Commands 下分活跃区和隔离区
- 按来源筛选：ECC / Gstack / Superpowers / 独立
- 按名称搜索（实时过滤）

### 2. 详情
- 显示名称、类型、来源、描述
- 预览 SKILL.md / agent 配置内容
- 复制路径

### 3. 搬家
- 活跃区 → 隔离区（带确认对话框）
- 隔离区 → 活跃区（带确认对话框）
- 操作日志写入 `~/.claude/skills-manager.log`

### 4. 来源标记
- 每个配置项通过 `.source` 文件标记来源
- 支持存量标注和后续自动化

## 不做的事（v1）

- 不编辑 SKILL.md 内容（用现有编辑器更好）
- 不安装/卸载技能（保持简单）
- 不管理 MCP 服务器（后续版本）
- 不管理多个 Claude Code 项目（仅全局 `~/.claude/`）
- 不做暗色模式（CSS 变量预留即可）
- 不做移动端适配

## 成功标准

- 打开浏览器 → 看到所有 296 项配置
- 搜索框输入 → 实时过滤
- 点击搬家按钮 → 确认 → 目录物理移动 → 列表刷新
- 关闭浏览器 → 无残留进程
