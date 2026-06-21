"""Workflow loading and topological sort."""

import json
from pathlib import Path
from collections import deque


def load(workflow_data: dict) -> dict:
    """Load and validate workflow data. Returns {nodes, edges, mode, ...} with sorted nodes."""
    nodes = workflow_data.get("nodes", [])
    edges = workflow_data.get("edges", [])
    if not nodes:
        raise ValueError("工作流没有节点")

    sorted_nodes = topological_sort(nodes, edges)
    return {
        "slug": workflow_data.get("slug", ""),
        "name": workflow_data.get("name", ""),
        "description": workflow_data.get("description", ""),
        "mode": workflow_data.get("mode", "auto"),
        "nodes": sorted_nodes,
        "edges": edges,
    }


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Sort nodes by edge dependencies using Kahn's algorithm."""
    node_map = {n["id"]: n for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        if frm in in_degree and to in in_degree:
            adjacency[frm].append(to)
            in_degree[to] += 1

    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    sorted_ids = []

    while queue:
        nid = queue.popleft()
        sorted_ids.append(nid)
        for neighbor in adjacency.get(nid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Nodes with no edges or circular dependencies — append in original order
    for nid in node_map:
        if nid not in sorted_ids:
            sorted_ids.append(nid)

    return [node_map[nid] for nid in sorted_ids]


def load_from_file(file_path: str) -> dict:
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    return load(data)
