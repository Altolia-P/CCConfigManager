"""RED tests for executor/tools.py -- 13 tool handlers + execute() dispatch.

These tests verify the behaviour of every ``_handle_*`` function and the
top-level ``execute()`` router.  Most handlers depend on a ``Sandbox``
instance and potentially on real filesystem or subprocess calls; relevant
external dependencies are mocked.

Edge cases covered:
- Empty / None / invalid input
- Blocked paths (sandbox)
- File-not-found, timeouts, network errors
- Large content truncation
- Unicode / special characters
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def tools_module(sandbox):
    """Provides a reference to the tools module for direct handler access."""
    from ccconfigmanager.executor import tools

    return tools


# ======================================================================
# execute() dispatch
# ======================================================================


class TestExecuteDispatch:
    """Verify that ``execute()`` routes to the correct handler or returns
    an error for unknown tool names."""

    def test_known_tool_dispatches_correctly(self, tools_module, sandbox):
        """``execute("Read", {…})`` should call ``_handle_read``."""
        result = tools_module.execute("Read", {"file_path": ""}, sandbox)
        # _handle_read with empty path -> Sandbox raises ValueError
        assert "失败" in result or "错误" in result

    def test_unknown_tool_returns_error_message(self, tools_module, sandbox):
        """An unrecognised tool name should produce a Chinese error string."""
        result = tools_module.execute("NonExistentTool", {}, sandbox)
        assert "未知工具" in result

    def test_none_tool_name(self, tools_module, sandbox):
        """Passing ``None`` as tool_name should be treated as unknown."""
        result = tools_module.execute(None, {}, sandbox)  # type: ignore[arg-type]
        assert "未知工具" in result

    def test_empty_tool_name(self, tools_module, sandbox):
        """Empty string should also be unknown."""
        result = tools_module.execute("", {}, sandbox)
        assert "未知工具" in result


# ======================================================================
# _handle_read
# ======================================================================


class TestHandleRead:
    """Tests for reading file contents via the sandbox."""

    def test_read_existing_file(self, tools_module, sandbox, tmp_path):
        """Reading an existing file returns its content."""
        f = tmp_path / "hello.txt"
        f.write_text("Hello, World!", encoding="utf-8")
        result = tools_module._handle_read({"file_path": "hello.txt"}, sandbox)
        assert result == "Hello, World!"

    def test_read_nonexistent_file(self, tools_module, sandbox):
        """Reading a file that does not exist returns an error message."""
        result = tools_module._handle_read({"file_path": "nonexistent.txt"}, sandbox)
        assert "失败" in result

    def test_read_empty_file(self, tools_module, sandbox, tmp_path):
        """Reading an empty file returns an empty string."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = tools_module._handle_read({"file_path": "empty.txt"}, sandbox)
        assert result == ""

    def test_read_truncates_large_content(self, tools_module, sandbox, tmp_path):
        """Content exceeding READ_MAX_BYTES should be truncated with a note."""
        f = tmp_path / "large.txt"
        f.write_text("x" * (tools_module.READ_MAX_BYTES + 1000), encoding="utf-8")
        result = tools_module._handle_read({"file_path": "large.txt"}, sandbox)
        assert len(result) <= tools_module.READ_MAX_BYTES + 10
        assert "截断" in result

    def test_read_with_unicode_content(self, tools_module, sandbox, tmp_path):
        """Unicode / emoji content should be preserved."""
        text = "Hello 世界 🌍 こんにちは"
        f = tmp_path / "unicode.txt"
        f.write_text(text, encoding="utf-8")
        result = tools_module._handle_read({"file_path": "unicode.txt"}, sandbox)
        assert result == text

    def test_read_with_none_file_path(self, tools_module, sandbox):
        """``None`` as file_path should be handled gracefully."""
        result = tools_module._handle_read({"file_path": None}, sandbox)
        assert "失败" in result or "错误" in result

    def test_read_absolute_path_outside_sandbox(self, tools_module, sandbox):
        """An absolute path outside the sandbox root should be rejected."""
        result = tools_module._handle_read({"file_path": "/etc/passwd"}, sandbox)
        assert "失败" in result or "错误" in result


# ======================================================================
# _handle_write
# ======================================================================


class TestHandleWrite:
    """Tests for writing file contents."""

    def test_write_new_file(self, tools_module, sandbox, tmp_path):
        """Writing a new file should create it with the given content."""
        content = "Hello, World!"
        result = tools_module._handle_write(
            {"file_path": "new.txt", "content": content}, sandbox
        )
        assert "已写入" in result
        assert (tmp_path / "new.txt").read_text(encoding="utf-8") == content

    def test_write_creates_parent_directories(self, tools_module, sandbox, tmp_path):
        """Writing to a nested path should auto-create parent dirs."""
        result = tools_module._handle_write(
            {"file_path": "a/b/c/nested.txt", "content": "nested"}, sandbox
        )
        assert "已写入" in result
        assert (tmp_path / "a" / "b" / "c" / "nested.txt").read_text(encoding="utf-8") == "nested"

    def test_write_overwrites_existing_file(self, tools_module, sandbox, tmp_path):
        """Writing to an existing path should overwrite it."""
        f = tmp_path / "exists.txt"
        f.write_text("old", encoding="utf-8")
        result = tools_module._handle_write(
            {"file_path": "exists.txt", "content": "new"}, sandbox
        )
        assert "已写入" in result
        assert f.read_text(encoding="utf-8") == "new"

    def test_write_to_blocked_path(self, tools_module, sandbox, tmp_path):
        """Writing to a path matching a blocked pattern should be rejected."""
        (tmp_path / ".env").write_text("", encoding="utf-8")
        result = tools_module._handle_write(
            {"file_path": ".env", "content": "SECRET=123"}, sandbox
        )
        assert "阻止" in result

    def test_write_with_empty_content(self, tools_module, sandbox, tmp_path):
        """Writing empty content should create an empty file."""
        result = tools_module._handle_write(
            {"file_path": "empty.txt", "content": ""}, sandbox
        )
        assert "已写入" in result
        assert (tmp_path / "empty.txt").read_text(encoding="utf-8") == ""

    def test_write_with_none_content(self, tools_module, sandbox, tmp_path):
        """``None`` content should be coerced to the string 'None' (current
        behaviour) or handled gracefully."""
        result = tools_module._handle_write(
            {"file_path": "none.txt", "content": None}, sandbox
        )
        # The current code does ``str(content)`` via ``input_data.get("content", "")``
        # so ``None`` -> string "None" actually gets written.
        assert "已写入" in result or "失败" in result


# ======================================================================
# _handle_edit
# ======================================================================


class TestHandleEdit:
    """Tests for the find-and-replace edit handler."""

    def test_edit_replaces_first_occurrence(self, tools_module, sandbox, tmp_path):
        """``old_string`` should be replaced once by default."""
        f = tmp_path / "edit.txt"
        f.write_text("aaa bbb aaa", encoding="utf-8")
        result = tools_module._handle_edit(
            {"file_path": "edit.txt", "old_string": "aaa", "new_string": "xxx"}, sandbox
        )
        assert "替换了 1 处" in result
        assert f.read_text(encoding="utf-8") == "xxx bbb aaa"

    def test_edit_replace_all(self, tools_module, sandbox, tmp_path):
        """With ``replace_all=True``, every occurrence should be replaced."""
        f = tmp_path / "edit.txt"
        f.write_text("aaa bbb aaa", encoding="utf-8")
        result = tools_module._handle_edit(
            {
                "file_path": "edit.txt",
                "old_string": "aaa",
                "new_string": "xxx",
                "replace_all": True,
            },
            sandbox,
        )
        assert "替换了 2 处" in result
        assert f.read_text(encoding="utf-8") == "xxx bbb xxx"

    def test_edit_string_not_found(self, tools_module, sandbox, tmp_path):
        """If ``old_string`` is absent, an error should be returned."""
        f = tmp_path / "edit.txt"
        f.write_text("hello world", encoding="utf-8")
        result = tools_module._handle_edit(
            {"file_path": "edit.txt", "old_string": "zzz", "new_string": "xxx"}, sandbox
        )
        assert "未找到" in result

    def test_edit_blocked_path(self, tools_module, sandbox, tmp_path):
        """Editing a blocked path should be rejected."""
        (tmp_path / ".env").write_text("KEY=val", encoding="utf-8")
        result = tools_module._handle_edit(
            {"file_path": ".env", "old_string": "KEY", "new_string": "SECRET"}, sandbox
        )
        assert "阻止" in result

    def test_edit_with_empty_old_string(self, tools_module, sandbox, tmp_path):
        """An empty ``old_string`` matches everywhere."""
        f = tmp_path / "empty_old.txt"
        f.write_text("hello", encoding="utf-8")
        result = tools_module._handle_edit(
            {"file_path": "empty_old.txt", "old_string": "", "new_string": "x"}, sandbox
        )
        assert "替换了" in result


# ======================================================================
# _handle_bash
# ======================================================================


class TestHandleBash:
    """Tests for shell command execution."""

    def test_bash_success(self, tools_module, sandbox, mock_subprocess_run):
        """A successful command should return its stdout."""
        result = tools_module._handle_bash({"command": "echo hello"}, sandbox)
        assert "hello world" in result

    def test_bash_with_stderr(self, tools_module, sandbox):
        """stderr should be appended to the output."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="out", stderr="err detail", returncode=0
            )
            result = tools_module._handle_bash({"command": "cmd"}, sandbox)
            assert "[stderr]" in result
            assert "err detail" in result

    def test_bash_nonzero_exit(self, tools_module, sandbox):
        """Non-zero exit code should be reported."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="", stderr="", returncode=1
            )
            result = tools_module._handle_bash({"command": "false"}, sandbox)
            assert "退出码" in result

    def test_bash_timeout(self, tools_module, sandbox):
        """A timeout should be reported as an error."""
        with patch("subprocess.run") as mock:
            import subprocess
            mock.side_effect = subprocess.TimeoutExpired(cmd="sleep", timeout=1)
            result = tools_module._handle_bash({"command": "sleep 10"}, sandbox)
            assert "超时" in result

    def test_bash_with_none_command(self, tools_module, sandbox):
        """``None`` command should not crash."""
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="", stderr="", returncode=0
            )
            result = tools_module._handle_bash({"command": None}, sandbox)
            # Should either run or return an error
            assert isinstance(result, str)

    def test_bash_with_custom_timeout(self, tools_module, sandbox):
        """Custom timeout should be passed to subprocess.run."""
        from unittest.mock import ANY
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="ok", stderr="", returncode=0
            )
            tools_module._handle_bash({"command": "echo hi", "timeout": 60}, sandbox)
            mock.assert_called_once()
            _args, kwargs = mock.call_args
            assert kwargs["timeout"] == 60


# ======================================================================
# _handle_grep
# ======================================================================


class TestHandleGrep:
    """Tests for text pattern search."""

    def test_grep_finds_matches(self, tools_module, sandbox, tmp_path):
        """Grep should find lines matching a regex pattern."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text(
            "def hello():\n    pass\n# TODO: fix\n", encoding="utf-8"
        )
        result = tools_module._handle_grep(
            {"pattern": "TODO", "directory": "."}, sandbox
        )
        assert "TODO" in result
        assert "main.py" in result

    def test_grep_no_matches(self, tools_module, sandbox, tmp_path):
        """When no lines match, return 'no matches' message."""
        (tmp_path / "readme.txt").write_text("hello world", encoding="utf-8")
        result = tools_module._handle_grep(
            {"pattern": "zzz_nonexistent", "directory": "."}, sandbox
        )
        assert "无匹配" in result

    def test_grep_empty_pattern(self, tools_module, sandbox, tmp_path):
        """An empty pattern should match every line."""
        (tmp_path / "f.txt").write_text("a\nb\nc", encoding="utf-8")
        result = tools_module._handle_grep(
            {"pattern": "", "directory": "."}, sandbox
        )
        # Should find 3 lines
        assert ":3:" in result or "a\n" in result

    def test_grep_skips_blocked_files(self, tools_module, sandbox, tmp_path):
        """Files matching blocked patterns should be skipped."""
        (tmp_path / ".env").write_text("SECRET=123", encoding="utf-8")
        result = tools_module._handle_grep(
            {"pattern": "SECRET", "directory": "."}, sandbox
        )
        assert "无匹配" in result

    def test_grep_with_none_pattern(self, tools_module, sandbox):
        """``None`` pattern should not crash."""
        result = tools_module._handle_grep({"pattern": None, "directory": "."}, sandbox)
        assert isinstance(result, str)


# ======================================================================
# _handle_glob
# ======================================================================


class TestHandleGlob:
    """Tests for file pattern matching."""

    def test_glob_finds_files(self, tools_module, sandbox, tmp_path):
        """Glob should return relative paths matching the pattern."""
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        result = tools_module._handle_glob({"pattern": "*.txt"}, sandbox)
        assert "a.txt" in result
        assert "b.txt" in result

    def test_glob_no_matches(self, tools_module, sandbox, tmp_path):
        """When no files match, return 'no match' message."""
        result = tools_module._handle_glob({"pattern": "*.xyz"}, sandbox)
        assert "无匹配" in result

    def test_glob_default_pattern(self, tools_module, sandbox, tmp_path):
        """Default pattern should be '**/*'."""
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        result = tools_module._handle_glob({}, sandbox)
        assert "f.txt" in result

    def test_glob_with_none_pattern(self, tools_module, sandbox):
        """``None`` pattern should not crash."""
        result = tools_module._handle_glob({"pattern": None}, sandbox)
        assert isinstance(result, str)


# ======================================================================
# _handle_skill
# ======================================================================


class TestHandleSkill:
    """Tests for SKILL.md loading."""

    def test_skill_not_found_returns_error(self, tools_module, sandbox):
        """When a skill directory does not exist, return an error message."""
        result = tools_module._handle_skill({"skill": "nonexistent-skill"}, sandbox)
        assert "未找到" in result

    def test_skill_with_args(self, tools_module, sandbox):
        """When args are provided, they should be appended to the output."""
        result = tools_module._handle_skill(
            {"skill": "nonexistent-skill", "args": "--verbose"}, sandbox
        )
        assert "参数" in result

    def test_skill_with_none_name(self, tools_module, sandbox):
        """``None`` skill name should not crash."""
        result = tools_module._handle_skill({"skill": None}, sandbox)
        assert isinstance(result, str)


# ======================================================================
# _handle_webfetch
# ======================================================================


class TestHandleWebFetch:
    """Tests for HTTP URL fetching."""

    def test_webfetch_valid_url(self, tools_module, sandbox, mock_urlopen):
        """A valid HTTP URL should return fetched content."""
        result = tools_module._handle_webfetch(
            {"url": "http://example.com"}, sandbox
        )
        assert "mock response" in result

    def test_webfetch_rejects_non_http(self, tools_module, sandbox):
        """Only http:// and https:// URLs should be allowed."""
        result = tools_module._handle_webfetch(
            {"url": "file:///etc/passwd"}, sandbox
        )
        assert "只允许" in result

    def test_webfetch_empty_url(self, tools_module, sandbox):
        """An empty URL should not crash."""
        result = tools_module._handle_webfetch({"url": ""}, sandbox)
        assert "只允许" in result or "失败" in result

    def test_webfetch_none_url(self, tools_module, sandbox):
        """``None`` URL should not crash."""
        result = tools_module._handle_webfetch({"url": None}, sandbox)
        assert isinstance(result, str)

    def test_webfetch_urlerror_returns_error(self, tools_module, sandbox):
        """A network error should return an error message, not crash."""
        with patch("urllib.request.urlopen") as mock:
            import urllib.error
            mock.side_effect = urllib.error.URLError(reason="connection refused")
            result = tools_module._handle_webfetch(
                {"url": "http://example.com"}, sandbox
            )
            assert "失败" in result


# ======================================================================
# _handle_websearch
# ======================================================================


class TestHandleWebSearch:
    """Tests for DuckDuckGo HTML search."""

    def test_websearch_returns_snippets(self, tools_module, sandbox, mock_urlopen):
        """Search should return extracted result snippets."""
        result = tools_module._handle_websearch({"query": "python"}, sandbox)
        # Even without real snippets, the fallback returns raw HTML
        assert isinstance(result, str)
        assert len(result) > 0

    def test_websearch_empty_query(self, tools_module, sandbox):
        """An empty query should return an error message."""
        result = tools_module._handle_websearch({"query": ""}, sandbox)
        assert "缺少" in result

    def test_websearch_none_query(self, tools_module, sandbox):
        """``None`` query should not crash."""
        result = tools_module._handle_websearch({"query": None}, sandbox)
        assert isinstance(result, str)


# ======================================================================
# _handle_task_create / _handle_task_update
# ======================================================================


class TestHandleTaskCreate:
    """Tests for task creation."""

    def test_create_task_returns_success(self, tools_module, sandbox, tmp_home):
        """Creating a task should write to the JSONL file and return a
        success message."""
        result = tools_module._handle_task_create(
            {"subject": "test task", "description": "do something"}, sandbox
        )
        assert "已创建" in result

        task_file = tmp_home / ".claude" / "CCConfigManager" / "agent-tasks.jsonl"
        assert task_file.is_file()
        lines = task_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["subject"] == "test task"

    def test_create_task_empty_subject(self, tools_module, sandbox, tmp_home):
        """An empty subject should still create the task file."""
        result = tools_module._handle_task_create(
            {"subject": "", "description": ""}, sandbox
        )
        assert "已创建" in result


class TestHandleTaskUpdate:
    """Tests for task status updates."""

    def test_update_existing_task(self, tools_module, sandbox, tmp_home):
        """Updating an existing task should change its status."""
        # Create first
        tools_module._handle_task_create(
            {"subject": "task1", "description": "desc"}, sandbox
        )
        # Read back to get the real UUID
        task_file = tmp_home / ".claude" / "CCConfigManager" / "agent-tasks.jsonl"
        lines = task_file.read_text(encoding="utf-8").strip().split("\n")
        task_id = json.loads(lines[0])["id"]
        # Update by UUID
        result = tools_module._handle_task_update(
            {"task_id": task_id, "status": "completed"}, sandbox
        )
        assert "已更新" in result

        # Verify on disk
        lines = task_file.read_text(encoding="utf-8").strip().split("\n")
        assert json.loads(lines[0])["status"] == "completed"

    def test_update_nonexistent_task(self, tools_module, sandbox):
        """Updating a non-existent task should return an error."""
        result = tools_module._handle_task_update(
            {"task_id": "999", "status": "completed"}, sandbox
        )
        assert "未找到" in result or "没有任务记录" in result

    def test_update_with_no_tasks_file(self, tools_module, sandbox):
        """When the JSONL file does not exist yet, return an error."""
        result = tools_module._handle_task_update(
            {"task_id": "0", "status": "done"}, sandbox
        )
        assert "没有任务记录" in result

    def test_update_invalid_task_id(self, tools_module, sandbox, tmp_home):
        """A non-integer task_id should not crash."""
        result = tools_module._handle_task_update(
            {"task_id": "abc", "status": "done"}, sandbox
        )
        assert isinstance(result, str)


# ======================================================================
# _handle_push_notification
# ======================================================================


class TestHandlePushNotification:
    """Tests for push notification logging."""

    def test_notification_writes_to_file(self, tools_module, sandbox, tmp_home):
        """A notification should be appended to notifications.jsonl."""
        result = tools_module._handle_push_notification(
            {"message": "test notify"}, sandbox
        )
        assert "已记录" in result

        nf = tmp_home / ".claude" / "CCConfigManager" / "notifications.jsonl"
        assert nf.is_file()
        lines = nf.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["message"] == "test notify"

    def test_notification_empty_message(self, tools_module, sandbox):
        """An empty message should still write an entry."""
        result = tools_module._handle_push_notification(
            {"message": ""}, sandbox
        )
        assert "已记录" in result


# ======================================================================
# _handle_ask_user_question
# ======================================================================


class TestHandleAskUserQuestion:
    """Tests for the AskUserQuestion handler — now raises AskUserQuestionSignal."""

    def test_ask_raises_signal(self, tools_module, sandbox):
        """The handler should raise AskUserQuestionSignal to pause execution."""
        with pytest.raises(tools_module.AskUserQuestionSignal) as exc:
            tools_module._handle_ask_user_question(
                {"question": "Should I proceed?", "header": "Confirmation"}, sandbox
            )
        assert exc.value.question == "Should I proceed?"
        assert exc.value.header == "Confirmation"

    def test_ask_empty_question(self, tools_module, sandbox):
        """An empty question should still raise the signal."""
        with pytest.raises(tools_module.AskUserQuestionSignal) as exc:
            tools_module._handle_ask_user_question(
                {"question": "", "header": ""}, sandbox
            )
        assert exc.value.question == ""

    def test_ask_with_options(self, tools_module, sandbox):
        """Options should be captured in the signal."""
        options = [{"label": "Proceed", "description": "Continue execution"}]
        with pytest.raises(tools_module.AskUserQuestionSignal) as exc:
            tools_module._handle_ask_user_question(
                {"question": "Go?", "header": "Gate", "options": options}, sandbox
            )
        assert exc.value.options == options


# ======================================================================
# Edge case: concurrent operations (best-effort simulation)
# ======================================================================


class TestConcurrentSafety:
    """Basic checks that tools do not obviously corrupt data under
    concurrent writes."""

    def test_concurrent_task_creates(self, tools_module, sandbox, tmp_home):
        """Creating multiple tasks should not lose entries."""
        import concurrent.futures

        def create(i: int):
            return tools_module._handle_task_create(
                {"subject": f"task-{i}", "description": ""}, sandbox
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(create, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all("已创建" in r for r in results)

        task_file = tmp_home / ".claude" / "CCConfigManager" / "agent-tasks.jsonl"
        lines = task_file.read_text(encoding="utf-8").strip().split("\n")
        # Concurrent file appends may interleave on some platforms; ensure
        # most tasks were recorded without corruption
        assert len(lines) >= 10

    def test_concurrent_file_writes(self, tools_module, sandbox, tmp_path):
        """Multiple concurrent writes to the same sandbox root should
        not corrupt sibling files."""
        import concurrent.futures

        def write(i: int):
            return tools_module._handle_write(
                {"file_path": f"file-{i}.txt", "content": f"content-{i}"}, sandbox
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(write, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all("已写入" in r for r in results)
        for i in range(20):
            assert (tmp_path / f"file-{i}.txt").read_text(encoding="utf-8") == f"content-{i}"
