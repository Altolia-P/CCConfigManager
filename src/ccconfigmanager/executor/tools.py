"""Core tool implementations for workflow agent execution."""

import json
import re
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from .sandbox import Sandbox

READ_MAX_BYTES = 200_000
BASH_TIMEOUT = 120
WEBFETCH_TIMEOUT = 30


class AskUserQuestionSignal(Exception):
    """Raised by AskUserQuestion handler to pause execution for user input."""
    def __init__(self, question: str, header: str = "", options: list[dict] | None = None):
        self.question = question
        self.header = header
        self.options = options or []
        super().__init__(f"AskUserQuestion: {header}")


def execute(tool_name: str, tool_input: dict, sandbox: Sandbox) -> str:
    handlers = {
        "Read": _handle_read,
        "Write": _handle_write,
        "Edit": _handle_edit,
        "Bash": _handle_bash,
        "Skill": _handle_skill,
        "WebFetch": _handle_webfetch,
        "WebSearch": _handle_websearch,
        "TaskCreate": _handle_task_create,
        "TaskUpdate": _handle_task_update,
        "Glob": _handle_glob,
        "Grep": _handle_grep,
        "PushNotification": _handle_push_notification,
        "AskUserQuestion": _handle_ask_user_question,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return f"未知工具: {tool_name}"
    return handler(tool_input, sandbox)


def _handle_read(input_data: dict, sandbox: Sandbox) -> str:
    try:
        file_path = sandbox.resolve_safe(input_data.get("file_path") or "")
        if sandbox.is_blocked(str(file_path)):
            return f"读取被阻止: {file_path}"
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = f"[二进制文件, {file_path.stat().st_size} bytes]"
        if len(content) > READ_MAX_BYTES:
            content = content[:READ_MAX_BYTES] + "\n...[截断]"
        return content
    except Exception as e:
        return f"读取文件失败: {e}"


def _handle_write(input_data: dict, sandbox: Sandbox) -> str:
    file_path = sandbox.resolve_safe(input_data.get("file_path", ""))
    if sandbox.is_blocked(str(file_path)):
        return f"写入被阻止: {file_path}"
    content = input_data.get("content", "")
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"已写入 {file_path} ({len(content)} 字符)"
    except Exception as e:
        return f"写入文件失败: {e}"


def _handle_bash(input_data: dict, sandbox: Sandbox) -> str:
    command = input_data.get("command", "")
    timeout = input_data.get("timeout", BASH_TIMEOUT)
    try:
        result = subprocess.run(
            command, shell=True, cwd=str(sandbox.project_root),
            capture_output=True, text=True, timeout=timeout, encoding="utf-8",
        )
        out = result.stdout
        if result.stderr:
            out += "\n[stderr]\n" + result.stderr
        if result.returncode != 0:
            out += f"\n[退出码: {result.returncode}]"
        return out or "(无输出)"
    except subprocess.TimeoutExpired:
        return f"命令超时 ({timeout}s): {command}"
    except Exception as e:
        return f"执行命令失败: {e}"


def _handle_grep(input_data: dict, sandbox: Sandbox) -> str:
    pattern = input_data.get("pattern", "")
    directory = input_data.get("directory", ".")
    try:
        safe_dir = sandbox.resolve_safe(directory)
        results = []
        for f in safe_dir.rglob("*"):
            if not f.is_file() or sandbox.is_blocked(str(f)):
                continue
            try:
                text = f.read_text(encoding="utf-8")
                for i, line in enumerate(text.splitlines()):
                    if re.search(pattern, line):
                        results.append(f"{f}:{i+1}: {line[:200]}")
            except Exception:
                pass
        return "\n".join(results[:100]) or "无匹配项"
    except Exception as e:
        return f"搜索失败: {e}"


def _handle_glob(input_data: dict, sandbox: Sandbox) -> str:
    pattern = input_data.get("pattern", "**/*")
    try:
        matches = list(sandbox.project_root.glob(pattern))
        result = [str(m.relative_to(sandbox.project_root))
                  for m in matches[:100] if not sandbox.is_blocked(str(m))]
        return "\n".join(result) or "无匹配文件"
    except Exception as e:
        return f"Glob 失败: {e}"


def _handle_edit(input_data: dict, sandbox: Sandbox) -> str:
    try:
        file_path = sandbox.resolve_safe(input_data.get("file_path") or "")
        if sandbox.is_blocked(str(file_path)):
            return f"编辑被阻止: {file_path}"
        old_string = input_data.get("old_string", "")
        new_string = input_data.get("new_string", "")
        replace_all = input_data.get("replace_all", False)
        content = file_path.read_text(encoding="utf-8")
        if old_string not in content:
            return f"未找到要替换的文本: {old_string[:80]}..."
        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1
        file_path.write_text(new_content, encoding="utf-8")
        return f"已编辑 {file_path}: 替换了 {count} 处"
    except Exception as e:
        return f"编辑文件失败: {e}"


def _handle_skill(input_data: dict, sandbox: Sandbox) -> str:
    skill_name = input_data.get("skill") or ""
    skill_args = input_data.get("args") or ""
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return f"非法 Skill 名称: {skill_name}"
    skill_md = Path.home() / ".claude" / "skills" / skill_name / "SKILL.md"
    if skill_md.is_file():
        content = skill_md.read_text(encoding="utf-8")[:20_000]
        result = f"Skill: {skill_name}\n{content}"
    else:
        result = f"Skill 未找到: {skill_name}"
    if skill_args:
        result += f"\n[参数: {skill_args}]"
    return result


def _handle_websearch(input_data: dict, sandbox: Sandbox) -> str:
    query = input_data.get("query", "")
    if not query:
        return "缺少搜索关键词"
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; WorkflowExecutor/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=WEBFETCH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        snippets = []
        # Match result__snippet content (text inside, until next HTML tag or result block)
        for m in re.finditer(r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)>', body, re.DOTALL):
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if text and len(text) > 10:
                snippets.append(text)
        if snippets:
            return "\n\n".join(snippets[:10])
        # Fallback: strip all tags and return body preview
        fallback = re.sub(r'<[^>]+>', ' ', body)
        fallback = re.sub(r'\s+', ' ', fallback).strip()
        return f"搜索结果（原始）: {fallback[:5_000]}"
    except Exception as e:
        return f"搜索失败: {e}"


def _get_task_file() -> Path:
    return Path.home() / ".claude" / "CCConfigManager" / "agent-tasks.jsonl"


import uuid as _uuid

def _handle_task_create(input_data: dict, sandbox: Sandbox) -> str:
    subject = input_data.get("subject", "")
    description = input_data.get("description", "")
    task = {"id": str(_uuid.uuid4())[:8], "subject": subject, "description": description, "status": "pending"}
    try:
        tf = _get_task_file()
        tf.parent.mkdir(parents=True, exist_ok=True)
        with open(tf, "a", encoding="utf-8") as f:
            f.write(json.dumps(task, ensure_ascii=False) + "\n")
        return f"已创建任务: {subject}"
    except Exception as e:
        return f"创建任务失败: {e}"


def _handle_task_update(input_data: dict, sandbox: Sandbox) -> str:
    task_id = input_data.get("task_id", "")
    new_status = input_data.get("status", "")
    tf = _get_task_file()
    if not tf.is_file():
        return "没有任务记录"
    try:
        lines = tf.read_text(encoding="utf-8").strip().split("\n")
        for i, line in enumerate(lines):
            try:
                task = json.loads(line)
            except Exception:
                continue
            if task.get("id") == task_id:
                task["status"] = new_status
                lines[i] = json.dumps(task, ensure_ascii=False)
                tf.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return f"任务 {task_id} 状态已更新为 {new_status}"
        return f"任务 {task_id} 未找到"
    except Exception as e:
        return f"更新任务失败: {e}"


def _handle_push_notification(input_data: dict, sandbox: Sandbox) -> str:
    message = input_data.get("message", "")
    notify_file = Path.home() / ".claude" / "CCConfigManager" / "notifications.jsonl"
    try:
        from datetime import datetime, timezone
        notify_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {"message": message, "timestamp": datetime.now(timezone.utc).isoformat()}
        with open(notify_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return f"通知已记录: {message}"


def _handle_ask_user_question(input_data: dict, sandbox: Sandbox) -> str:
    question = input_data.get("question", "")
    header = input_data.get("header", "")
    options = input_data.get("options", None)
    raise AskUserQuestionSignal(question, header, options)


WEBFETCH_MAX_BYTES = 500_000

def _handle_webfetch(input_data: dict, sandbox: Sandbox) -> str:
    url = input_data.get("url") or ""
    if not url.startswith(("http://", "https://")):
        return "只允许 HTTP/HTTPS URL"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WorkflowExecutor/1.0"})
        with urllib.request.urlopen(req, timeout=WEBFETCH_TIMEOUT) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > WEBFETCH_MAX_BYTES:
                return f"响应过大 ({content_length} bytes)，上限 {WEBFETCH_MAX_BYTES}"
            body = resp.read(WEBFETCH_MAX_BYTES + 1)
            if len(body) > WEBFETCH_MAX_BYTES:
                body = body[:WEBFETCH_MAX_BYTES]
            return body.decode("utf-8", errors="replace")[:50_000]
    except urllib.error.URLError as e:
        return f"请求失败: {e}"
    except Exception as e:
        return f"获取失败: {e}"
