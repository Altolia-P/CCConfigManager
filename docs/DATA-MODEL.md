# DATA MODEL — 数据模型

## 目录结构约定

所有配置在 `~/.claude/` 下：

```
~/.claude/
├── skills/              # 活跃 Skills（目录）
│   ├── investigate/
│   │   ├── SKILL.md
│   │   └── .source      # ecc
│   └── gstack/          # Gstack skill 套件（git repo）
│       ├── SKILL.md.tmpl
│       └── .source      # gstack
├── skills-archive/      # 隔离 Skills（目录）
│   ├── cpp-coding-standards/
│   │   └── .source      # ecc
│   └── ...
├── agents/              # 活跃 Agents（文件）
│   ├── code-reviewer.md
│   ├── .code-reviewer.source
│   └── ...
├── agents-archive/      # 隔离 Agents（文件）
│   ├── cpp-build-resolver.md
│   ├── .cpp-build-resolver.source
│   └── ...
├── commands/            # 活跃 Commands（文件）
│   ├── review.md
│   ├── .review.source
│   └── ...
├── commands-archive/    # 隔离 Commands
│   └── ...
├── rules/               # 活跃 Rules（递归子目录，每个 .md 是一个 item）
│   ├── zh/              # 通用规则（中文）
│   │   ├── coding-style.md
│   │   ├── .coding-style.source
│   │   └── ...
│   ├── java/            # Java 规则
│   ├── kotlin/          # Kotlin 规则
│   └── python/          # Python 规则
├── rules-archive/       # 隔离 Rules（同结构）
│   ├── common/
│   ├── csharp/
│   ├── golang/
│   └── ...
├── plugins/             # Claude Code 插件系统
│   ├── installed_plugins.json
│   └── cache/           # 插件缓存的 skills/agents/...（scanner 动态纳入）
└── ecc/
    └── install-state.json  # ECC 安装清单（454 条操作记录）
```

## 核心数据结构

### Item（统一模型）

```python
@dataclass
class Item:
    type: str           # "skill" | "agent" | "command" | "rule"
    name: str           # skill=目录名, agent/cmd=文件名(无扩展名), rule="子目录/文件名"
    source: str         # 动态来源标识（见下），不枚举
    status: str         # "active" | "archived"
    path: str           # 绝对路径
    paths: list[str]    # 多路径（插件+固定路径去重后）
    description: str    # 从 SKILL.md 或 .md 前几行提取的描述
    content_preview: str # 文件前 20 行
```

### 示例

```json
{
    "type": "skill",
    "name": "investigate",
    "source": "ecc",
    "status": "active",
    "paths": ["~/.claude/skills/investigate"],
    "description": "系统调试技能，四阶段方法论",
    "content_preview": "---\nname: investigate\n..."
}
```

```json
{
    "type": "rule",
    "name": "java/testing",
    "source": "ecc",
    "status": "active",
    "paths": ["~/.claude/rules/java/testing.md"],
    "description": "Java 测试最佳实践...",
    "content_preview": "# Java 测试规则\n..."
}
```

## 来源识别（核心设计）

### 设计原则

不硬编码路径、不依赖人工标注、不假定目录结构。来源由"安装方式"反推。

### 识别流程（优先级从高到低）

```
扫描到一个 item
  │
  ├─ 1. 读 .source 文件（缓存快速路径）
  │     已存在 → 直接返回，跳过后续检测
  │     不存在 → 继续
  │
  ├─ 2. 插件系统检测
  │     读 ~/.claude/plugins/installed_plugins.json
  │     item 路径在某个插件的 installPath 子树下？
  │     → 是 → 来源 = pluginId 中 @ 前的名字
  │
  ├─ 3. 安装清单检测
  │     遍历 ~/.claude/*/install-state.json
  │     item 路径在某个清单的 destinationPath 列表里？
  │     → 是 → 来源 = 清单所在目录名
  │
  ├─ 4. Git 仓库检测（预建缓存，非逐 item 调 git）
  │     启动时 walk 整棵树收集所有 git root，构建 {root_path: repo_name} 映射
  │     → item 路径前缀匹配 → 来源 = repo_name
  │
  └─ 5. 兜底
       以上都不命中 → 来源 = "standalone"
```

### 各层详解

#### 第 1 层：.source 缓存

首次扫描后写入 `.source` 文件，后续扫描 O(1) 读取，跳过昂贵检测。
用户想改来源 → 删 `.source` 文件重启 → 自动重检。

#### 第 2 层：插件系统

`installed_plugins.json` 是 Claude Code 维护的标准文件。提取 `@` 前的标识作为来源名，不硬编码任何插件名。

```json
{
  "plugins": {
    "superpowers@claude-plugins-official": [{
      "installPath": "~/.claude/plugins/cache/.../superpowers/5.1.0"
    }]
  }
}
```

#### 第 3 层：安装清单

ECC 在 `~/.claude/ecc/install-state.json` 记录了 454 条操作，每条含 `destinationPath`，精确到文件级别。扫描所有 `~/.claude/*/install-state.json`，查表匹配。
因为是文件级记录，手动新建的同目录 item 不会被误标。

#### 第 4 层：Git 仓库（预建映射）

**不在每个 item 上跑 git 命令。** 启动时 walk 一次目录树：

```python
def build_git_source_map(base_dir):
    repo_map = {}
    for root, dirs, files in os.walk(base_dir):
        if ".git" in dirs:
            url = git_remote_url(root)
            name = extract_repo_name(url)   # gstack, example-skills...
            repo_map[root] = name
            dirs.remove(".git")
    return repo_map
```

后续每个 item 做前缀匹配 `item_path.startswith(repo_root)` → O(n) 无系统调用。
当前实际命中：`skills/gstack/` → `gstack`（唯一 git repo）。

#### 第 5 层：兜底

用户手动创建的 skill → `standalone`。

### source 字段取值

```python
SourceValue = str  # 小写+连字符，不枚举
# 实际值示例: "ecc" | "gstack" | "superpowers" | "claude-mem" | "example-skills" | "standalone"
```

### .source 文件约定

| 类型 | .source 位置 | 示例 |
|------|-------------|------|
| Skill（目录） | `skill-name/.source` | `skills/investigate/.source` |
| Agent（文件） | `agents/.agent-name.source` | `agents/.code-reviewer.source` |
| Command（文件） | `commands/.cmd-name.source` | `commands/.review.source` |
| Rule（文件，任意深度） | 与 .md 文件同级 | `rules/zh/.coding-style.source`、`rules/java/.testing.source` |

内容：单行，小写，无空格，无换行。

Agent/Command/Rule 因为是单个 md 文件，`.source` 前缀 `.` + 文件名放在同级。
Rule 的 name 使用 `子目录/文件名` 格式（如 `zh/coding-style`、`java/testing`），保证唯一且可读。

## 描述提取规则

### Skill（目录类型）
1. 读 `SKILL.md` 前 20 行
2. 跳过 frontmatter（`---` 块）
3. 取第一个非空、非标题的文本行作为描述
4. 都找不到 → "无描述"

### Agent / Command（文件类型）
1. 读 `.md` 文件前 20 行
2. 同 skill 规则

### Rule（文件类型，任意深度）
1. 读 `.md` 文件前 20 行
2. 同 skill 规则

## 扫描路径

### 1. 固定路径

```
~/.claude/skills/          → type=skill,  status=active
~/.claude/skills-archive/  → type=skill,  status=archived
~/.claude/agents/          → type=agent,  status=active
~/.claude/agents-archive/  → type=agent,  status=archived
~/.claude/commands/        → type=command,status=active
~/.claude/commands-archive/→ type=command,status=archived
~/.claude/rules/           → type=rule,   status=active  (递归)
~/.claude/rules-archive/   → type=rule,   status=archived (递归)
```

### 2. 插件路径（installed_plugins.json → 动态）

对每个插件的 `installPath`，检查并纳入：

```
{installPath}/skills/   → type=skill,  status=active
{installPath}/agents/   → type=agent,  status=active
{installPath}/commands/ → type=command,status=active
{installPath}/rules/    → type=rule,   status=active
```

四种类型都扫，不假定插件只提供 skill。

### 规则

- Rules 递归扫描所有子目录，不限制深度
- 跳过 `.` 开头的文件/目录（`.git`、`.agents` 等）
- 只处理 `.md` 文件（Agent/Command/Rule）
- 去重：同名 item 出现在多个路径 → 合并为一条，paths 列表去重
- 插件 item 的 status 始终为 `active`（插件无隔离区概念），source 由第 2 层自动判定
