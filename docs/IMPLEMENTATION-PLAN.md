# IMPLEMENTATION PLAN — 实现计划

## 阶段 2.5：用后端脚本执行 Phase 0（前置清理）

> 此时 source_detector.py 和 mover.py 已就绪，用它们完成前置工作，不做一次性脚本。

### 2.5.1 批量标注来源
- [ ] 运行 source_detector 对所有 item 执行三层检测
- [ ] 为每个 item 写入 `.source` 文件
- [ ] 验证：所有 item 的 source 字段不为 `unknown`

### 2.5.2 散落归位
- [ ] `.agents/skills/` 34 个 skill 去重：
  - 14 个与活跃区重复 → 丢弃 `.agents/` 版本
  - 4 个有用独有（claude-api, documentation-lookup, everything-claude-code, security-review） → 迁入活跃区
  - 16 个不相关（article-writing, brand-voice, video-editing 等） → 标记来源后移入隔离区
- [ ] marketplace 17 个 skill（algorithmic-art, docx, pptx 等） → 全部标记 `example-skills`，移入隔离区
- [ ] cpp/dart 一致性：rules/cpp/ rules/dart/ 已移入 rules-archive/，agents-archive/ 已创建，
      commands 中 cpp/flutter 已移入 commands-archive/（已完成于 2026-06-17）
- [ ] 验证：`.agents/skills/` 目录清空，marketplace skills 目录清空

### 2.5.3 验证
- [ ] `python -c "from scanner import scan_all; print(len(scan_all()))"` → 活跃+隔离总数正确
- [ ] 抽查 5 个 item 的 `.source` 文件内容正确
- [ ] 抽查 3 个搬家 item 物理路径正确
- [ ] 搬家日志 `~/.claude/skills-manager.log` 记录完整

## 阶段 1：骨架（约 30 分钟）

### 1.1 项目初始化
- [ ] 创建 `D:\Desktop\project-manager\` 目录
- [ ] 写入 `requirements.txt`（fastapi, uvicorn）
- [ ] 创建 `app.py` 骨架（FastAPI 实例化，CORS 中间件，挂载 static）
- [ ] 创建 `static/index.html` 骨架（空白页面，"Hello Project Manager"）
- [ ] `pip install -r requirements.txt && python app.py` → 浏览器看到页面

### 1.2 验收
```
curl http://localhost:8899/ → 返回 HTML 页面
curl http://localhost:8899/api/types → ["skills", "agents", "commands", "rules"]
```

## 阶段 2：后端核心（约 1 小时）

### 2.1 扫描器（scanner.py）
- [ ] `get_scan_paths()` — 固定路径（含 `agents-archive/`）+ `installed_plugins.json` 动态生成
- [ ] 每个插件路径检查 `skills/` `agents/` `commands/` `rules/` 四种子目录是否存在
- [ ] `scan_skills(paths)` — 扫描所有 skills 源路径，去重
- [ ] `scan_agents(paths)` — 扫描所有 agents 源路径（含 `agents-archive/`）
- [ ] `scan_commands(paths)` — 扫描所有 commands 源路径
- [ ] `scan_rules(paths)` — 递归扫描所有 rules 源路径，name 格式 `子目录/文件名`
- [ ] 每个 item：读 `.source`（缓存路径），读文件前 20 行提取描述，构建 Item
- [ ] 去重：同一名称的 item 出现在多个路径 → 保留一条，记录路径列表

### 2.1a 来源检测器（source_detector.py）
- [ ] `detect_source(item_path)` — 按四层顺序检测，返回来源字符串
- [ ] 第 1 层：读 `.source` 文件（快速路径，已存在则直接返回）
- [ ] 第 2 层：读 `installed_plugins.json`，路径前缀匹配 installPath
- [ ] 第 3 层：扫描 `~/.claude/*/install-state.json`，查 destinationPath 表（文件级精确匹配）
- [ ] 第 4 层：Git 仓库检测——启动时 `build_git_source_map()` 预建 `{root: name}` 映射，
      后续 item 前缀匹配 O(1)，不逐 item 调 git
- [ ] 兜底：返回 `"standalone"`
- [ ] 检测完成后自动写 `.source` 文件（缓存加速后续扫描）
- [ ] Git map 构建：walk 目录树 → 找到 `.git` → `git remote get-url origin` → 提取仓库名

### 2.2 API 路由（app.py）
- [ ] `GET /api/types` — 返回支持的类型列表
- [ ] `GET /api/items?type=skills&source=ecc&status=active&search=xxx`
- [ ] `GET /api/item/{type}/{name}` — 返回单个 item 详情 + 内容预览
- [ ] `GET /api/stats` — 返回各类型活跃/隔离/来源统计

### 2.3 搬家（mover.py）
- [ ] `POST /api/move` — 接收 `{type, name, to}`
- [ ] 路径映射：`{type}_DIR[to]` 查表（skill→skills/skills-archive, agent→agents/agents-archive, etc.）
- [ ] 验证源路径存在，目标路径不冲突
- [ ] 同时移动配套 `.source` 文件
- [ ] `shutil.move()` 执行移动
- [ ] 追加日志到 `~/.claude/skills-manager.log`
- [ ] `GET /api/logs` — 返回最近日志

### 2.4 验收
```
curl http://localhost:8899/api/items?type=skills | python -m json.tool
# 返回 107+ 个 skill 的 JSON 数组
curl -X POST http://localhost:8899/api/move -H "Content-Type: application/json" -d '{"type":"skill","name":"test-xxx","to":"archived"}'
# 返回成功/失败
```

## 阶段 3：前端（约 1.5 小时）

### 3.1 HTML 结构
- [ ] 顶部搜索栏
- [ ] 三栏布局（导航 / 列表 / 详情）
- [ ] 底部统计栏

### 3.2 左侧导航
- [ ] 类型列表渲染（从 /api/stats 获取）
- [ ] 点击切换类型
- [ ] 来源筛选 checkbox
- [ ] 状态筛选 checkbox

### 3.3 中间列表
- [ ] 调用 /api/items 获取数据
- [ ] 渲染列表项（名称 + 描述 + 来源标签 + 状态图标）
- [ ] 点击选中 → 加载详情
- [ ] 搜索框实时过滤（300ms 防抖）

### 3.4 右侧详情
- [ ] 默认状态提示
- [ ] 选中后渲染：名称、类型、来源、状态、路径、描述、内容预览
- [ ] 搬家按钮 + 确认对话框
- [ ] 复制路径按钮
- [ ] 搬家成功后刷新列表

### 3.5 验收
```
浏览器打开 → 看到 Skills 列表 → 搜索 "debug" → 列表过滤 → 
点击 investigate → 右侧显示详情 → 点"移到隔离区" → 确认 → 
列表更新 → 去 ~/.claude/skills-archive/ 验证文件已移动
```

## 阶段 4：打磨（约 30 分钟）

### 4.1 边界情况
- [ ] 搜索无结果时的空状态
- [ ] API 请求失败时的错误提示 + 重试
- [ ] 加载中的骨架屏或 spinner
- [ ] 搬家操作中的按钮禁用（防重复点击）
- [ ] 搬家失败时的错误信息展示

### 4.2 体验优化
- [ ] 来源标签颜色
- [ ] 活跃/隔离状态图标
- [ ] 列表项 hover 效果
- [ ] 选中项高亮
- [ ] `Ctrl+K` 聚焦搜索框
- [ ] `Esc` 清除搜索
- [ ] 搬家成功后 500ms toast 提示

### 4.3 验收
```
完整走一遍浏览→搜索→查看详情→搬家→验证→搬回来的流程，无报错，无闪烁
```

## 阶段 5：提交（约 15 分钟）

- [ ] `requirements.txt` 完整
- [ ] 代码无硬编码路径（全部从 `~/.claude` 动态获取）
- [ ] `python app.py` 一条命令启动
- [ ] 端口 8899 可改（环境变量 `PORT`）
- [ ] 关闭时无残留进程

## 禁止事项

- ❌ 不要引入 React/Vue/npm/webpack/TypeScript
- ❌ 不要引入数据库或 ORM
- ❌ 不要做用户认证/登录
- ❌ 不要做多项目切换
- ❌ 不要写超过 300 行的单文件
- ❌ 不要用 `print()` 代替日志
- ❌ 不要硬编码 Windows 路径（用 `os.path.expanduser("~")`）
