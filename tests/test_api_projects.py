"""RED tests for routes/proj.py -- project CRUD, sync, discover, copy-to-project.

All tests use the ``client`` fixture with HOME pointing to an isolated
``tmp_path``.  Projects data lives in ``tmp_path/.claude/CCConfigManager/projects.json``.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ======================================================================
# GET /api/projects -- list all
# ======================================================================


class TestListProjects:
    """List all registered projects."""

    def test_empty_when_no_projects(self, client):
        """With no projects, should return an empty object."""
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) == 0

    def test_after_creating_project(self, client):
        """After creating a project, it should appear in the list."""
        client.post("/api/projects", json={"name": "my-project", "path": "/tmp/test-path"})
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert "my-project" in data

    def test_multiple_projects(self, client):
        """Multiple projects should all appear."""
        client.post("/api/projects", json={"name": "proj-a", "path": "/tmp/a"})
        client.post("/api/projects", json={"name": "proj-b", "path": "/tmp/b"})
        resp = client.get("/api/projects")
        assert len(resp.json()) == 2


# ======================================================================
# POST /api/projects -- create
# ======================================================================


class TestCreateProject:
    """Create a new project."""

    def test_create_success(self, client):
        """Creating a valid project should return success."""
        resp = client.post("/api/projects", json={"name": "new-project", "path": "/tmp/proj"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "已创建" in data.get("message", "")

    def test_create_duplicate(self, client):
        """Creating a project with a duplicate name should fail."""
        client.post("/api/projects", json={"name": "dup", "path": "/tmp/dup"})
        resp = client.post("/api/projects", json={"name": "dup", "path": "/tmp/dup-other"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False
        assert "已存在" in data.get("message", "")

    def test_create_empty_name(self, client):
        """Creating a project with an empty name should be handled."""
        resp = client.post("/api/projects", json={"name": "", "path": "/tmp/empty"})
        # May succeed (empty string is a valid key) or fail
        assert resp.status_code in (200, 422)

    def test_create_missing_path(self, client):
        """Creating a project without a path should still work (path='')."""
        resp = client.post("/api/projects", json={"name": "no-path"})
        assert resp.status_code == 200


# ======================================================================
# DELETE /api/projects/{name}
# ======================================================================


class TestDeleteProject:
    """Delete a project."""

    def test_delete_existing(self, client):
        """Deleting an existing project should return success."""
        client.post("/api/projects", json={"name": "to-delete", "path": "/tmp/x"})
        resp = client.delete("/api/projects/to-delete")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert "已删除" in data.get("message", "")

    def test_delete_nonexistent(self, client):
        """Deleting a non-existing project should return success=False."""
        resp = client.delete("/api/projects/does-not-exist")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_delete_empty_name(self, client):
        """Deleting with an empty name should not crash."""
        resp = client.delete("/api/projects/")
        assert resp.status_code in (200, 404, 405)

    def test_delete_then_list(self, client):
        """After deletion, the project should disappear from the list."""
        client.post("/api/projects", json={"name": "temp", "path": "/tmp/t"})
        client.delete("/api/projects/temp")
        resp = client.get("/api/projects")
        assert "temp" not in resp.json()


# ======================================================================
# POST /api/projects/{name}/items -- add item to project
# ======================================================================


class TestAddProjectItem:
    """Add a config item reference to a project."""

    def test_add_item_to_existing_project(self, client):
        """Adding an item to an existing project should succeed."""
        client.post("/api/projects", json={"name": "p", "path": "/tmp/p"})
        resp = client.post(
            "/api/projects/p/items",
            json={"type": "skill", "item_name": "my-skill"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

    def test_add_item_to_nonexistent_project(self, client):
        """Adding an item to a non-existent project should fail."""
        resp = client.post(
            "/api/projects/no-such/items",
            json={"type": "skill", "item_name": "s"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_add_duplicate_item(self, client):
        """Adding the same item twice should return success=False."""
        client.post("/api/projects", json={"name": "p2", "path": "/tmp/p2"})
        client.post("/api/projects/p2/items", json={"type": "skill", "item_name": "dup"})
        resp = client.post(
            "/api/projects/p2/items",
            json={"type": "skill", "item_name": "dup"},
        )
        data = resp.json()
        assert data.get("success") is False
        assert "已在项目中" in data.get("message", "")

    def test_add_item_empty_name(self, client):
        """Adding an item with an empty name should not crash."""
        client.post("/api/projects", json={"name": "p3", "path": "/tmp/p3"})
        resp = client.post(
            "/api/projects/p3/items",
            json={"type": "skill", "item_name": ""},
        )
        assert resp.status_code in (200, 422)


# ======================================================================
# DELETE /api/projects/{name}/items -- remove item from project
# ======================================================================


class TestRemoveProjectItem:
    """Remove a config item reference from a project."""

    def test_remove_existing_item(self, client):
        """Removing an existing item should succeed."""
        client.post("/api/projects", json={"name": "p", "path": "/tmp/p"})
        client.post("/api/projects/p/items", json={"type": "skill", "item_name": "s"})
        resp = client.request(
            "DELETE",
            "/api/projects/p/items",
            json={"type": "skill", "item_name": "s"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

    def test_remove_nonexistent_item(self, client):
        """Removing an item that was never added should fail."""
        client.post("/api/projects", json={"name": "p", "path": "/tmp/p"})
        resp = client.request(
            "DELETE",
            "/api/projects/p/items",
            json={"type": "skill", "item_name": "not-added"},
        )
        data = resp.json()
        assert data.get("success") is False


# ======================================================================
# POST /api/projects/{name}/sync
# ======================================================================


class TestSyncProject:
    """Sync a project with filesystem state."""

    def test_sync_nonexistent_project(self, client):
        """Syncing a non-existent project should fail."""
        resp = client.post("/api/projects/no-such/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_sync_project_no_claude_dir(self, client):
        """Syncing a project whose path has no .claude/ returns empty scan."""
        client.post("/api/projects", json={"name": "empty-proj", "path": "/tmp/nonexistent"})
        resp = client.post("/api/projects/empty-proj/sync")
        assert resp.status_code == 200


# ======================================================================
# POST /api/projects/{name}/discover
# ======================================================================


class TestDiscoverProject:
    """Auto-discover config items for a project."""

    def test_discover_nonexistent_project(self, client):
        """Discovering on a non-existent project should fail."""
        resp = client.post("/api/projects/no-such/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_discover_no_project_dir(self, client):
        """Discovering on a project with no actual directory should fail."""
        client.post("/api/projects", json={"name": "no-dir", "path": "/tmp/nonexistent-dir"})
        resp = client.post("/api/projects/no-dir/discover")
        data = resp.json()
        assert data.get("success") is False

    def test_discover_empty_project(self, client, tmp_path):
        """Discovering on an empty project directory should find nothing."""
        proj_dir = tmp_path / "my-project"
        proj_dir.mkdir()
        client.post("/api/projects", json={"name": "my-project", "path": str(proj_dir)})
        resp = client.post("/api/projects/my-project/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True


# ======================================================================
# POST /api/projects/{name} -- get single project (via projects_data.get)
# ======================================================================


class TestGetProjectItem:
    """GET /api/project-items -- list items for a project path."""

    def test_project_items_empty_path(self, client):
        """An empty path should return an empty list."""
        resp = client.get("/api/project-items?path=")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_project_items_nonexistent_path(self, client):
        """A path with no .claude directory returns empty."""
        resp = client.get("/api/project-items?path=/tmp/nonexistent")
        assert resp.status_code == 200
        assert resp.json() == []


# ======================================================================
# POST /api/copy-to-project
# ======================================================================


class TestCopyToProject:
    """Copy a config item into a project's .claude/."""

    def test_copy_missing_parameters(self, client):
        """Missing any required parameter should return an error."""
        resp = client.post("/api/copy-to-project", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False
        assert "缺少参数" in data.get("message", "")

    def test_copy_nonexistent_item(self, client, tmp_path):
        """Copying a non-existent item should fail."""
        proj_dir = tmp_path / "target-project"
        proj_dir.mkdir()
        resp = client.post(
            "/api/copy-to-project",
            json={
                "project_path": str(proj_dir),
                "type": "rule",
                "name": "nonexistent-rule",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False

    def test_copy_path_outside_home(self, client):
        """A project path outside $HOME should be rejected."""
        resp = client.post(
            "/api/copy-to-project",
            json={
                "project_path": "/etc/malicious",
                "type": "rule",
                "name": "test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is False
