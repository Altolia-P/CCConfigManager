"""Workflow execution engine — orchestrates node execution."""

import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import run_store, workflow_loader, agent_runner, hooks, gate, produces
from .sandbox import Sandbox

# Ensure only one run per workflow slug at a time
_active_runs: set[str] = set()
_active_lock = threading.Lock()

ASK_QUESTION_MARKER = "[WORKFLOW_ASK_USER_QUESTION]"


def execute_async(workflow_json: dict, project_name: str, project_path: str,
                  max_tool_rounds: int = 30, initial_message: str = "") -> str:
    """Start async workflow execution. Returns run_id immediately.

    initial_message is the optional external trigger message — it becomes the
    first agent node's user input (e.g. from a webhook or API call).

    Raises RuntimeError if a run for this workflow slug is already in progress.
    """
    wf = workflow_loader.load(workflow_json)
    slug = wf["slug"]

    with _active_lock:
        if slug in _active_runs:
            # Check if the existing run is actually still active
            stale = True
            try:
                existing = run_store.list_runs(None)
                for r in existing:
                    if r.get("workflow_slug") == slug and r.get("status") in ("running", "waiting_approval", "waiting_confirmation"):
                        stale = False
                        break
            except Exception:
                pass
            if stale:
                _active_runs.discard(slug)
            else:
                raise RuntimeError(f"工作流 '{slug}' 已有运行在进行中，请等待完成后重试")
        _active_runs.add(slug)

    node_ids = [n["id"] for n in wf["nodes"]]
    run_id = run_store.create(slug, project_name, project_path, node_ids,
                              initial_message=initial_message)

    thread = threading.Thread(
        target=_execute,
        args=(wf, project_name, project_path, run_id, max_tool_rounds),
        kwargs={"prev_output": initial_message},
        daemon=True,
    )
    thread.start()
    return run_id


def _execute(wf: dict, project_name: str, project_path: str, run_id: str,
             max_tool_rounds: int, prev_output: str = "") -> None:
    import json as _json
    sandbox = Sandbox(project_path)
    pending_approval = False

    try:
        for node in wf["nodes"]:
            run_store.update(run_id, current_node=node["id"])

            # --- Gate node ---
            if node.get("type") == "gate":
                gcfg = node.get("gateConfig", {})
                result = gate.check(prev_output, gcfg)
                if result == "manual":
                    run_store.update(run_id, status="waiting_approval",
                                     current_node=node["id"])
                    run_store.update_node(run_id, node["id"],
                                          status="waiting_approval")
                    pending_approval = True
                    return  # Wait for manual approval
                elif result == "fail":
                    run_store.fail(run_id, f"门禁未通过: {node['label']}")
                    return
                run_store.update_node(run_id, node["id"],
                                      status="completed", output=f"门禁通过: {result}")
                continue

            # --- Hook (onEnter) ---
            if node.get("type") in ("agent", "command"):
                node_hooks = node.get("hooks", [])
                if node_hooks:
                    try:
                        hresults = hooks.execute(node_hooks, "onEnter", project_path,
                                                 prev_output, _node_context(node))
                        for hr in hresults:
                            hr["node_id"] = node["id"]
                            run_store.add_hook_result(run_id, hr)
                    except hooks.HookFailed:
                        run_store.fail(run_id, f"节点 {node['label']} 的 onEnter Hook 失败")
                        return

            # --- Agent / Command node ---
            if node.get("type") in ("agent", "command"):
                ts = datetime.now(timezone.utc).isoformat()
                run_store.update_node(run_id, node["id"], status="running", started_at=ts)

                agent_id = node.get("agentId")
                if not agent_id:
                    run_store.update_node(run_id, node["id"],
                                          status="completed", output="(未指定 Agent，跳过)")
                    continue

                user_msg = prev_output
                if user_msg:
                    user_msg += "\n\n---\n"
                user_msg += f"当前任务: {node.get('label', '执行步骤')}"

                # Inject command content if commandId is set
                command_id = node.get("commandId")
                if command_id:
                    cmd_content = _load_command_content(command_id)
                    if cmd_content:
                        user_msg += f"\n\n<command name=\"{command_id}\">\n{cmd_content}\n</command>"

                output = agent_runner.run(
                    agent_id=agent_id,
                    skill_ids=node.get("skillIds") or [],
                    mcp_ids=node.get("mcpIds") or [],
                    tool_ids=node.get("toolIds") or [],
                    node_permissions=node.get("permissions"),
                    user_message=user_msg,
                    sandbox=sandbox,
                    max_rounds=node.get("maxToolRounds", max_tool_rounds),
                    timeout_minutes=node.get("timeout", None) or 10,
                    run_id=run_id,
                )

                # Check if agent paused for a question
                if output.startswith(ASK_QUESTION_MARKER):
                    question_json = output[len(ASK_QUESTION_MARKER):].strip()
                    question_data = _json.loads(question_json)
                    run_store.set_pending_question(run_id, node["id"], question_data)
                    run_store.update(run_id, status="waiting_question",
                                     current_node=node["id"])
                    run_store.update_node(run_id, node["id"],
                                          status="waiting_question",
                                          output=output)
                    return  # Wait for user answer

                # --- Produces check (before prev_output so next node sees it) ---
                produces_list = node.get("produces", [])
                if produces_list:
                    presults = produces.check(produces_list, project_path)
                    run_store.add_produces_result(run_id, node["id"], presults)
                    missing = [r["name"] for r in presults if not r["exists"]]
                    output += f"\n\n[产出文件检查: {len(presults)} 项]"
                    if missing:
                        output += f"\n⚠ 缺失产出: {', '.join(missing)}"

                prev_output = output

                ts = datetime.now(timezone.utc).isoformat()
                run_store.update_node(run_id, node["id"],
                                      status="completed", output=output,
                                      finished_at=ts)

                # --- Hook (onLeave) ---
                if node.get("hooks"):
                    try:
                        hresults = hooks.execute(node["hooks"], "onLeave", project_path,
                                                 prev_output, _node_context(node))
                        for hr in hresults:
                            hr["node_id"] = node["id"]
                            run_store.add_hook_result(run_id, hr)
                    except hooks.HookFailed:
                        run_store.fail(run_id, f"节点 {node['label']} 的 onLeave Hook 失败")
                        return

            # --- Edge check for manual advance (check all outgoing edges) ---
            if any(e.get("condition") == "manual" for e in wf["edges"] if e.get("from") == node["id"]):
                run_store.update(run_id, status="waiting_confirmation")
                return

        run_store.complete(run_id)

    except Exception as e:
        run_store.fail(run_id, str(e))
        # Mark the current node as failed too
        rd = run_store.get(run_id)
        cn = rd.get("current_node")
        if cn:
            run_store.update_node(run_id, cn, status="failed", output=str(e))
    finally:
        with _active_lock:
            _active_runs.discard(wf.get("slug", ""))


def continue_run(run_id: str, project_path: str, max_tool_rounds: int = 30,
                 user_answer: str | None = None) -> str:
    """Continue a run paused at a manual gate/edge/question, or retry a failed run."""
    import json as _json
    data = run_store.get(run_id)
    status = data["status"]
    allowed = ("waiting_approval", "waiting_confirmation", "failed", "waiting_question")
    if status not in allowed:
        return f"Run 当前状态不允许继续: {status}"

    # Handle AskUserQuestion resume
    if status == "waiting_question" and user_answer is not None:
        pq = data.get("pending_question")
        if not pq:
            return "没有待回答问题"
        ckpt_id = pq.get("checkpoint_id")
        if not ckpt_id:
            return "检查点 ID 缺失"
        node_id = pq.get("node_id")

        sandbox = Sandbox(project_path)
        with _active_lock:
            _active_runs.add(data["workflow_slug"])

        run_store.update(run_id, status="running")
        if node_id:
            run_store.update_node(run_id, node_id, status="running")

        output = agent_runner.resume_from_question(ckpt_id, user_answer, sandbox)

        # Check for follow-up questions
        if output.startswith(ASK_QUESTION_MARKER):
            question_json = output[len(ASK_QUESTION_MARKER):].strip()
            question_data = _json.loads(question_json)
            run_store.set_pending_question(run_id, node_id, question_data)
            run_store.update(run_id, status="waiting_question",
                             current_node=node_id)
            if node_id:
                run_store.update_node(run_id, node_id, status="waiting_question",
                                      output=output)
            return f"Agent 继续提问"

        # Agent finished — update node and continue workflow
        if node_id:
            ts = datetime.now(timezone.utc).isoformat()
            run_store.update_node(run_id, node_id,
                                  status="completed", output=output,
                                  finished_at=ts)

        # Continue with remaining nodes
        from ..registry import CLAUDE_DIR
        wf_file = Path(CLAUDE_DIR) / "workflows" / f"{data['workflow_slug']}.json"
        if not wf_file.is_file():
            return "工作流文件不存在"
        workflow_json = _json.loads(wf_file.read_text(encoding="utf-8"))
        wf = workflow_loader.load(workflow_json)

        # Find the node index and continue from next
        start_idx = 0
        for i, node in enumerate(wf["nodes"]):
            if node["id"] == node_id:
                start_idx = i + 1
                break

        wf_sliced = {
            "slug": wf["slug"], "name": wf["name"],
            "description": wf["description"], "mode": wf["mode"],
            "nodes": wf["nodes"][start_idx:], "edges": wf["edges"],
        }

        thread = threading.Thread(
            target=_execute,
            args=(wf_sliced, data["project_name"], project_path, run_id, max_tool_rounds),
            kwargs={"prev_output": output},
            daemon=True,
        )
        thread.start()
        return "已回答，工作流继续执行"

    from ..registry import CLAUDE_DIR
    wf_file = Path(CLAUDE_DIR) / "workflows" / f"{data['workflow_slug']}.json"
    if not wf_file.is_file():
        return "工作流文件不存在"
    workflow_json = _json.loads(wf_file.read_text(encoding="utf-8"))
    wf = workflow_loader.load(workflow_json)

    last_output = ""
    start_index = 0
    if status == "failed":
        # Re-acquire the lock for retry
        with _active_lock:
            _active_runs.add(wf["slug"])
        # Find the failed node and resume from it
        for i, node in enumerate(wf["nodes"]):
            node_state = data["nodes"].get(node["id"], {})
            if node_state.get("status") in ("running", "failed"):
                # Reset this node and start here
                run_store.update_node(run_id, node["id"], status="pending",
                                      output=None, started_at=None, finished_at=None)
                start_index = i
                break
            if node_state.get("status") == "completed":
                last_output = node_state.get("output", "")
        # Also reset the run-level status
        run_store.update(run_id, status="running", error=None)
    else:
        # Find last completed node to resume from
        for i, node in enumerate(wf["nodes"]):
            node_state = data["nodes"].get(node["id"], {})
            if node_state.get("status") == "completed":
                last_output = node_state.get("output", "")
                start_index = i + 1
            elif node_state.get("status") == "waiting_approval":
                # Manual gate was approved — mark completed and move past it
                run_store.update_node(run_id, node["id"],
                                      status="completed", output="门禁通过: manual (已批准)")
                start_index = i + 1
                break
            else:
                start_index = i
                break

        # Re-lock the slug for continued execution
        with _active_lock:
            if wf["slug"] in _active_runs:
                # Already locked from the original execute_async — nothing to do
                pass
            else:
                _active_runs.add(wf["slug"])

        run_store.update(run_id, status="running")

    wf_sliced = {
        "slug": wf["slug"], "name": wf["name"],
        "description": wf["description"], "mode": wf["mode"],
        "nodes": wf["nodes"][start_index:], "edges": wf["edges"],
    }

    thread = threading.Thread(
        target=_execute,
        args=(wf_sliced, data["project_name"], project_path, run_id, max_tool_rounds),
        kwargs={"prev_output": last_output},
        daemon=True,
    )
    thread.start()
    action = "已重试" if status == "failed" else "已恢复执行"
    return f"Run {action}"


def _node_context(node: dict) -> dict:
    """Extract skill/mcp/tool/permission context from a node dict for hook execution."""
    return {
        "skill_ids": node.get("skillIds") or [],
        "mcp_ids": node.get("mcpIds") or [],
        "tool_ids": node.get("toolIds") or [],
        "permissions": node.get("permissions"),
    }


def _load_command_content(command_name: str) -> str:
    cmd_file = Path(os.path.expanduser(f"~/.claude/commands/{command_name}.md"))
    if cmd_file.is_file():
        return cmd_file.read_text(encoding="utf-8")
    return ""
