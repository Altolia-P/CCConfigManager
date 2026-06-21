"""Agent config routes — per-agent model, API key, base_url settings."""

from fastapi import APIRouter

from ..executor import save_agent_config, get_agent_config

router = APIRouter(tags=["agents"])


@router.get("/api/agent-configs")
def list_configs():
    from ..executor.agent_runner import _load_agent_config
    return {"success": True, "data": _load_agent_config()}


@router.post("/api/agent-config/{agent_name}")
def save(agent_name: str, body: dict):
    save_agent_config(agent_name, body)
    return {"success": True, "message": f"已保存 Agent 配置: {agent_name}"}


@router.get("/api/agent-config/{agent_name}")
def get(agent_name: str):
    return {"success": True, "data": get_agent_config(agent_name)}
