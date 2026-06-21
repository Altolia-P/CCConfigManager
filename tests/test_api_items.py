"""RED tests for routes/items.py -- core config item CRUD endpoints.

These tests use the ``client`` fixture which provides a FastAPI TestClient
with HOME pointing to an isolated ``tmp_path`` containing an empty
``~/.claude/`` skeleton.

Because the scanner will see no real config files and the registry is
monkeypatched, all endpoints work against an empty state.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ======================================================================
# GET /
# ======================================================================


class TestIndex:
    """Root endpoint returns the static frontend HTML."""

    def test_index_returns_html(self, client):
        """GET / should return an HTML page."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "").lower()


# ======================================================================
# GET /api/types
# ======================================================================


class TestGetTypes:
    """Type listing endpoint."""

    def test_returns_type_list(self, client):
        """GET /api/types should return the full type list."""
        resp = client.get("/api/types")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "skills" in data
        assert "agents" in data
        assert "commands" in data
        assert "rules" in data
        assert "mcps" in data
        assert "tools" in data
        assert "workflows" in data

    def test_returns_correct_count(self, client):
        """There should be exactly 8 types."""
        resp = client.get("/api/types")
        assert len(resp.json()) == 8


# ======================================================================
# GET /api/items
# ======================================================================


class TestGetItems:
    """Config item listing with filtering."""

    def test_returns_empty_list_when_no_items(self, client):
        """With no config files, GET /api/items should return []."""
        resp = client.get("/api/items")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_items_by_type(self, client):
        """Passing ?type=skills should filter by type."""
        resp = client.get("/api/items?type=skills")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_returns_items_by_status(self, client):
        """Passing ?status=active should filter by status."""
        resp = client.get("/api/items?status=active")
        assert resp.status_code == 200

    def test_returns_items_by_source(self, client):
        """Passing ?source=standalone should filter by source."""
        resp = client.get("/api/items?source=standalone")
        assert resp.status_code == 200

    def test_returns_items_by_search(self, client):
        """Passing ?search=test should search name+description."""
        resp = client.get("/api/items?search=test")
        assert resp.status_code == 200

    def test_returns_items_combined_filters(self, client):
        """Multiple query parameters should combine."""
        resp = client.get("/api/items?type=skills&status=active&source=standalone&search=test")
        assert resp.status_code == 200

    def test_invalid_type_returns_empty(self, client):
        """An unknown type should return an empty list."""
        resp = client.get("/api/items?type=nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []


# ======================================================================
# GET /api/item/{type}/{name}
# ======================================================================


class TestGetItem:
    """Single item detail endpoint."""

    def test_item_not_found_returns_404(self, client):
        """A non-existent item should return 404."""
        resp = client.get("/api/item/skill/nonexistent-skill")
        assert resp.status_code == 404

    def test_item_not_found_has_error_message(self, client):
        """404 response should contain a message."""
        resp = client.get("/api/item/skill/nonexistent-skill")
        data = resp.json()
        assert "未找到" in data.get("message", "")

    def test_item_with_special_chars_in_name(self, client):
        """Item names with special characters should be URL-encoded."""
        resp = client.get("/api/item/skill/100%25%20test")
        # 404 is fine (item doesn't exist); the point is no 500
        assert resp.status_code in (200, 404)


# ======================================================================
# POST /api/items/batch
# ======================================================================


class TestBatchItems:
    """Batch item lookup."""

    def test_batch_with_empty_body(self, client):
        """Empty items list should return empty array."""
        resp = client.post("/api/items/batch", json={"items": []})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_batch_with_missing_items_key(self, client):
        """Missing 'items' key should be treated as empty."""
        resp = client.post("/api/items/batch", json={})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_batch_with_invalid_json(self, client):
        """Invalid JSON body should return 422."""
        resp = client.post("/api/items/batch", content=b"not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422


# ======================================================================
# POST /api/move
# ======================================================================


class TestMoveItem:
    """Item move (active <-> archive) endpoint."""

    def test_move_nonexistent_item(self, client):
        """Moving a non-existent item should return success=False."""
        resp = client.post(
            "/api/move",
            json={"type": "skill", "name": "nonexistent", "to": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False
        assert "未找到" in data.get("message", "")

    def test_move_missing_fields(self, client):
        """Missing fields should be handled gracefully."""
        resp = client.post("/api/move", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_move_invalid_type(self, client):
        """An invalid type should not crash."""
        resp = client.post(
            "/api/move",
            json={"type": "invalid_type", "name": "test", "to": "active"},
        )
        assert resp.status_code in (200, 422)


# ======================================================================
# GET /api/stats
# ======================================================================


class TestGetStats:
    """Statistics endpoint."""

    def test_stats_empty_when_no_items(self, client):
        """With no config items, stats should be empty."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_stats_is_dict(self, client):
        """Stats response should be a dict."""
        resp = client.get("/api/stats")
        data = resp.json()
        assert isinstance(data, dict)


# ======================================================================
# GET /api/logs
# ======================================================================


class TestGetLogs:
    """Operation logs endpoint."""

    def test_logs_empty_when_no_logs(self, client):
        """With no move history, logs should be empty."""
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_logs_with_limit(self, client):
        """A custom limit should be accepted."""
        resp = client.get("/api/logs?limit=10")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ======================================================================
# PUT /api/item/{type}/{name}
# ======================================================================


class TestUpdateItem:
    """Item content / description update endpoint."""

    def test_update_nonexistent_item(self, client):
        """Updating a non-existent item should return success=False."""
        resp = client.put(
            "/api/item/skill/nonexistent",
            json={"content": "new content"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_update_empty_body(self, client):
        """An empty JSON body should not crash."""
        resp = client.put(
            "/api/item/skill/nonexistent",
            json={},
        )
        assert resp.status_code == 200


# ======================================================================
# POST /api/mcp/refresh-tools
# ======================================================================


class TestRefreshTools:
    """MCP tools cache refresh endpoint."""

    def test_refresh_returns_immediate_success(self, client):
        """The endpoint should return immediately with a background message."""
        resp = client.post("/api/mcp/refresh-tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "后台刷新" in data.get("message", "")
