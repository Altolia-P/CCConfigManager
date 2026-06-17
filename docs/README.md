# Project Manager — Claude Code 配置管理桌面工具

## 这是什么

一个 Web 界面的 Claude Code 配置管理工具，管理 Skills、Agents、Commands、Rules 的浏览、搜索、搬家（活跃区 ↔ 隔离区）。

## 文档索引

按顺序读：

| 顺序 | 文件 | 内容 |
|------|------|------|
| 1 | `PRD.md` | 产品定义、核心功能、不做的事 |
| 2 | `ARCHITECTURE.md` | 技术选型、目录结构、关键决策 |
| 3 | `DATA-MODEL.md` | 数据模型、.source 约定、目录结构 |
| 4 | `UI-SPEC.md` | 界面布局、交互逻辑、状态处理 |
| 5 | `IMPLEMENTATION-PLAN.md` | 分阶段实现步骤、验收标准 |

## 一句话总结

> 扫描 `~/.claude/` 下的 Skills/Agents/Commands/Rules，在浏览器里浏览搜索，一键在活跃区和隔离区之间移动。

## 当前配置体量

| 类型 | 活跃 | 隔离 |
|------|------|------|
| Skills | 107 | 19 |
| Agents | 49 | 0 |
| Commands | 53 | 28 |
| Rules | 10 | 40 |
