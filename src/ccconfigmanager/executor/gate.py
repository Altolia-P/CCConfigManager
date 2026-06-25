"""Gate condition checker.

Supports three gate conditions:
- manual: always pauses for user confirmation
- auto: sends question + context to Claude for YES/NO decision
- expression: evaluates locally using a simple expression parser;
  falls back to Claude for complex expressions
"""

import json
import os
import re
import threading
from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"

POSITIVE_MARKERS = ("YES", "YEP", "PASS", "CORRECT", "TRUE", "AFFIRMATIVE", "通过", "是")

_client: Anthropic | None = None
_client_key: str = ""
_client_lock = threading.Lock()


def _reset() -> None:
    """Clear the cached Anthropic client (for test isolation)."""
    global _client, _client_key
    with _client_lock:
        _client = None
        _client_key = ""


def _get_client() -> Anthropic:
    global _client, _client_key
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise ValueError("未设置 ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN")
    base_url = os.environ.get("ANTHROPIC_BASE_URL") or ""
    cache_key = f"{api_key}:{base_url}"
    if _client is None or _client_key != cache_key:
        with _client_lock:
            if _client is None or _client_key != cache_key:
                if base_url:
                    _client = Anthropic(api_key=api_key, base_url=base_url)
                else:
                    _client = Anthropic(api_key=api_key)
                _client_key = cache_key
    return _client


def _resolve_placeholders(expr: str, prev_output: str) -> str:
    """Replace {{output.key}} with the actual value from prev_output (JSON-parsed)."""
    result = expr.replace("{{output}}", prev_output).replace("{{prev_output}}", prev_output)

    def _replace_json_path(m: re.Match) -> str:
        keys = m.group(1).split(".")
        if keys[0] in ("output", "prev_output"):
            keys = keys[1:]
        if not keys:
            return prev_output
        try:
            data = json.loads(prev_output)
            for k in keys:
                if isinstance(data, dict):
                    data = data.get(k, "")
                elif isinstance(data, list) and k.isdigit():
                    idx = int(k)
                    data = data[idx] if 0 <= idx < len(data) else ""
                else:
                    return ""
            return json.dumps(data, ensure_ascii=False) if data is not None else '""'
        except (json.JSONDecodeError, TypeError, KeyError, IndexError):
            return ""

    result = re.sub(r"\{\{(output(?:\.[\w]+)+)\}\}", _replace_json_path, result)
    result = re.sub(r"\{\{(prev_output(?:\.[\w]+)+)\}\}", _replace_json_path, result)
    return result


def _eval_expression(expr: str, prev_output: str) -> bool | None:
    """Evaluate a simple gate expression. Returns True/False, or None if unparseable."""
    expr = _resolve_placeholders(expr, prev_output).strip()

    # --- Two-value comparisons ---
    m = re.match(r'^"(.+)"\s*==\s*"(.+)"$', expr)
    if m:
        return m.group(1) == m.group(2)

    m = re.match(r'^"(.+)"\s*!=\s*"(.+)"$', expr)
    if m:
        return m.group(1) != m.group(2)

    # --- Case-insensitive contains / not contains ---
    m = re.match(r'^(?:not|NOT|Not)\s+contains\s+"(.+)"$', expr)
    if m:
        return m.group(1) not in prev_output

    m = re.match(r'^contains\s+"(.+)"$', expr, re.IGNORECASE)
    if m:
        return m.group(1) in prev_output

    # --- Equality / inequality against prev_output ---
    m = re.match(r'^==\s+"(.+)"$', expr)
    if m:
        return prev_output.strip() == m.group(1)

    m = re.match(r'^!=\s+"(.+)"$', expr)
    if m:
        return prev_output.strip() != m.group(1)

    # --- Numeric comparisons (support negative numbers) ---
    for pattern, op_func in [
        (r'^>=\s*(-?[\d.]+)$', lambda a, b: a >= b),
        (r'^<=\s*(-?[\d.]+)$', lambda a, b: a <= b),
        (r'^>\s*(-?[\d.]+)$', lambda a, b: a > b),
        (r'^<\s*(-?[\d.]+)$', lambda a, b: a < b),
    ]:
        m = re.match(pattern, expr)
        if m:
            try:
                return op_func(float(prev_output.strip()), float(m.group(1)))
            except ValueError:
                return None

    # --- Empty / not empty ---
    if expr.lower() in ("not empty", "not blank", "非空"):
        return bool(prev_output.strip())

    if expr.lower() in ("empty", "blank", "为空"):
        return not bool(prev_output.strip())

    return None


def check(prev_output: str | None, gate_config: dict | None) -> str:
    """Check gate condition. Returns 'pass', 'fail', 'manual', or error message."""
    if gate_config is None:
        return "pass"

    if gate_config is not None and not isinstance(gate_config, dict):
        return f"门禁配置无效（非字典类型）: {type(gate_config).__name__}"

    prev_output = str(prev_output or "")
    condition = gate_config.get("condition", "auto")

    if condition == "manual":
        return "manual"

    if condition == "expression":
        expr = gate_config.get("expression", "")
        if not expr.strip():
            return "pass"
        result = _eval_expression(expr, prev_output)
        if result is True:
            return "pass"
        if result is False:
            return "fail"
        question = expr
    elif condition == "auto":
        question = gate_config.get("autoDetect", "")
    else:
        return f"未知门禁条件: {condition}"

    if not question.strip():
        return "pass"

    try:
        client = _get_client()
        model = os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
        response = client.messages.create(
            model=model,
            max_tokens=32,
            messages=[{
                "role": "user",
                "content": (
                    "你是一个门禁检查器。判断以下条件是否满足。\n"
                    "只回答 YES 或 NO，不要解释。\n\n"
                    f"条件: {question}\n\n"
                    f"上下文信息:\n{prev_output[:8000]}"
                )
            }],
            thinking={"type": "disabled"},
        )
        answer = "NO"
        for block in response.content:
            if hasattr(block, "text") and block.text:
                answer = block.text.strip().upper()
                break
        for marker in POSITIVE_MARKERS:
            if answer.startswith(marker):
                return "pass"
        return "fail"
    except Exception as e:
        return f"门禁检查失败: {e}"
