"""Permission filtering for workflow nodes."""

import fnmatch


def filter_tools(agent_tools: list[str], node_permissions: dict | None) -> list[str]:
    """Filter agent's declared tools against node permissions.
    Returns intersection of agent_tools + allows, minus blocks.
    Blocks take precedence over allows.
    """
    if not node_permissions or (not node_permissions.get("allows") and not node_permissions.get("blocks")):
        return list(agent_tools)

    allows = set(x for x in (node_permissions.get("allows") or []) if x is not None)
    blocks = set(x for x in (node_permissions.get("blocks") or []) if x is not None)

    result = set(agent_tools)

    if allows:
        result = result & allows

    # Direct matches (e.g. "Write", "Bash")
    for block in blocks:
        if "(" not in block:
            result.discard(block)

    return sorted(result)


def is_tool_allowed(tool_name: str, tool_input: dict, node_permissions: dict | None) -> bool:
    """Runtime check for parameterized blocks like 'Write(*.env)'.
    Uses fnmatch for glob patterns and only checks the primary path field,
    not all input values (to avoid false positives from content fields)."""
    if not node_permissions:
        return True

    blocks = node_permissions.get("blocks", []) or []
    for block in blocks:
        if "(" not in block:
            continue
        base, _, params = block.partition("(")
        params = params.rstrip(")")
        if base != tool_name:
            continue
        for pattern in [p.strip() for p in params.split(",")]:
            if pattern == "*":
                return False
            # Only check the primary path field, not content or other fields
            path_val = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("command") or ""
            if fnmatch.fnmatch(str(path_val), pattern):
                return False

    return True
