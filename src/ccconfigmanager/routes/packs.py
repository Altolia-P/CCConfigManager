"""Pack routes — curated config bundles."""

import json

from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse

from .. import packs as packs_data

router = APIRouter(tags=["packs"])


@router.get("/api/packs")
def list_all():
    return packs_data.list_all()


@router.post("/api/packs")
def create(body: dict):
    return packs_data.create(body.get("name", ""))


@router.delete("/api/packs/{name}")
def delete(name: str):
    return packs_data.delete(name)


@router.post("/api/packs/{name}/items")
def add_item(name: str, body: dict):
    return packs_data.add_item(name, body.get("type", ""), body.get("item_name", ""))


@router.delete("/api/packs/{name}/items")
def remove_item(name: str, body: dict):
    return packs_data.remove_item(name, body.get("type", ""), body.get("item_name", ""))


@router.get("/api/packs/{name}/export")
def export(name: str):
    data = packs_data._load().get("packs", {})
    if name not in data:
        return JSONResponse({"success": False, "message": "包不存在"}, status_code=404)
    content = json.dumps(data[name], indent=2, ensure_ascii=False)
    return Response(content, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pack.json"'})
