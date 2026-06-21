"""RED tests for executor/gate.py -- gate condition checker.

The ``check()`` function evaluates conditions ("manual", "auto", "expression")
and optionally queries the Anthropic API.  All Anthropic calls are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest


# ======================================================================
# _get_client
# ======================================================================


class TestGetClient:
    """Verify that the Anthropic client is created correctly."""

    def test_client_created_with_api_key(self, monkeypatch):
        """When ANTHROPIC_API_KEY is set, a client should be returned."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        from ccconfigmanager.executor.gate import _get_client

        client = _get_client()
        assert client is not None

    def test_client_raises_without_api_key(self, monkeypatch):
        """Without any API key env vars, _get_client should raise ValueError."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        from ccconfigmanager.executor.gate import _get_client

        with pytest.raises(ValueError, match="未设置"):
            _get_client()


# ======================================================================
# check() -- gate evaluation
# ======================================================================


class TestCheckManual:
    """Manual gates always return "manual"."""

    def test_manual_condition(self):
        """``condition: "manual"`` should immediately return "manual"."""
        from ccconfigmanager.executor.gate import check

        result = check("some previous output", {"condition": "manual"})
        assert result == "manual"

    def test_manual_ignores_empty_config(self):
        """Manual gate with no other fields should still work."""
        from ccconfigmanager.executor.gate import check

        result = check("", {"condition": "manual"})
        assert result == "manual"


class TestCheckAuto:
    """Auto gates use an Anthropic call with an autoDetect question."""

    def test_auto_pass_when_claude_says_yes(self, mock_anthropic_client):
        """If Claude responds YES, check() should return "pass"."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        result = check("output", {"condition": "auto", "autoDetect": "Is it done?"})
        assert result == "pass"

    def test_auto_fail_when_claude_says_no(self, mock_anthropic_client):
        """If Claude responds NO (or anything not starting with YES),
        check() should return "fail"."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="NO")
        ]
        result = check("output", {"condition": "auto", "autoDetect": "Is it done?"})
        assert result == "fail"

    def test_auto_empty_question_passes(self, mock_anthropic_client):
        """An empty autoDetect question should skip the API call and
        return "pass"."""
        from ccconfigmanager.executor.gate import check

        result = check("output", {"condition": "auto", "autoDetect": ""})
        assert result == "pass"

    def test_auto_question_is_whitespace_only(self, mock_anthropic_client):
        """Whitespace-only autoDetect should also pass without API call."""
        from ccconfigmanager.executor.gate import check

        result = check("output", {"condition": "auto", "autoDetect": "   "})
        assert result == "pass"

    def test_auto_truncates_prev_output(self, mock_anthropic_client):
        """Previous output longer than 8000 chars should be truncated."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]

        long_output = "x" * 10_000
        result = check(long_output, {"condition": "auto", "autoDetect": "Q?"})

        assert result == "pass"
        # Verify truncation in the message content
        call_kwargs = mock_anthropic_client.return_value.messages.create.call_args
        sent_content = call_kwargs[1]["messages"][0]["content"]
        assert len(sent_content) < len(long_output) + 200


class TestCheckExpression:
    """Expression gates evaluate locally; unparseable expressions fall back to Claude."""

    def test_expression_contains_pass(self):
        """``contains "text"`` should evaluate locally."""
        from ccconfigmanager.executor.gate import check

        result = check("error: something went wrong", {"condition": "expression", "expression": 'contains "error"'})
        assert result == "pass"

    def test_expression_contains_fail(self):
        """``contains`` with absent text should fail."""
        from ccconfigmanager.executor.gate import check

        result = check("all good", {"condition": "expression", "expression": 'contains "error"'})
        assert result == "fail"

    def test_expression_not_contains(self):
        """``not contains`` should pass when text is absent."""
        from ccconfigmanager.executor.gate import check

        result = check("all good", {"condition": "expression", "expression": 'not contains "error"'})
        assert result == "pass"

    def test_expression_eq_match(self):
        """``== "text"`` should match exact output."""
        from ccconfigmanager.executor.gate import check

        result = check("completed", {"condition": "expression", "expression": '== "completed"'})
        assert result == "pass"

    def test_expression_eq_no_match(self):
        """``== "text"`` should fail for mismatched output."""
        from ccconfigmanager.executor.gate import check

        result = check("running", {"condition": "expression", "expression": '== "completed"'})
        assert result == "fail"

    def test_expression_neq(self):
        """``!= "text"`` should pass for different output."""
        from ccconfigmanager.executor.gate import check

        result = check("running", {"condition": "expression", "expression": '!= "completed"'})
        assert result == "pass"

    def test_expression_gt_number(self):
        """``> N`` should compare numeric output."""
        from ccconfigmanager.executor.gate import check

        result = check("42", {"condition": "expression", "expression": "> 10"})
        assert result == "pass"

    def test_expression_lt_number_fail(self):
        """``< N`` should fail when number is larger."""
        from ccconfigmanager.executor.gate import check

        result = check("99", {"condition": "expression", "expression": "< 50"})
        assert result == "fail"

    def test_expression_not_empty(self):
        """``not empty`` should pass for non-empty output."""
        from ccconfigmanager.executor.gate import check

        result = check("some output", {"condition": "expression", "expression": "not empty"})
        assert result == "pass"

    def test_expression_empty(self):
        """``empty`` should pass for blank output."""
        from ccconfigmanager.executor.gate import check

        result = check("   ", {"condition": "expression", "expression": "empty"})
        assert result == "pass"

    def test_expression_json_path(self):
        """``{{output.status}}`` should extract JSON field."""
        from ccconfigmanager.executor.gate import check

        result = check('{"status": "completed", "count": 5}', {"condition": "expression", "expression": '{{output.status}} == "completed"'})
        assert result == "pass"

    def test_expression_unparseable_falls_back_to_claude(self, mock_anthropic_client):
        """Unparseable expressions should delegate to Claude."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        result = check("data", {"condition": "expression", "expression": "is this really done?"})
        assert result == "pass"

    def test_expression_empty_passes(self):
        """An empty expression should skip API and pass."""
        from ccconfigmanager.executor.gate import check

        result = check("data", {"condition": "expression", "expression": ""})
        assert result == "pass"


class TestCheckUnknown:
    """Unknown conditions should return an error message."""

    def test_unknown_condition_returns_error(self):
        """An unsupported condition value should return a Chinese error."""
        from ccconfigmanager.executor.gate import check

        result = check("output", {"condition": "unknown_type"})
        assert "未知" in result

    def test_missing_condition_key(self, mock_anthropic_client):
        """A gate config with no condition key defaults to auto."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        result = check("output", {"autoDetect": "Q"})
        # Defaults to auto condition when autoDetect is present
        assert result == "pass"

    def test_none_gate_config(self):
        """None as gate_config should pass through, not crash."""
        from ccconfigmanager.executor.gate import check

        result = check("output", None)  # type: ignore[arg-type]
        assert result == "pass"


# ======================================================================
# Edge cases
# ======================================================================


class TestCheckEdgeCases:
    """Additional edge-case checks."""

    def test_empty_prev_output(self, mock_anthropic_client):
        """Empty previous output should still be accepted."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        result = check("", {"condition": "auto", "autoDetect": "Is it done?"})
        assert result == "pass"

    def test_none_prev_output(self, mock_anthropic_client):
        """None previous output should be converted to string."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        # The function does str() on prev_output via f-string truncation
        result = check(None, {"condition": "auto", "autoDetect": "Is it done?"})  # type: ignore[arg-type]
        assert result == "pass"

    def test_unicode_in_question(self, mock_anthropic_client):
        """Unicode characters in the question should be handled."""
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]
        result = check(
            "output",
            {"condition": "auto", "autoDetect": "结果正确吗？ 🤔"},
        )
        assert result == "pass"

    def test_concurrent_checks(self, mock_anthropic_client):
        """Multiple parallel gate checks should not interfere."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from ccconfigmanager.executor.gate import check

        mock_anthropic_client.return_value.messages.create.return_value.content = [
            MagicMock(text="YES")
        ]

        def do_check(i: int):
            return check(
                f"output-{i}",
                {"condition": "auto", "autoDetect": f"Is step {i} done?"},
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(do_check, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        assert all(r == "pass" for r in results)
