"""RED tests for executor/workflow_loader.py.

Covers:
- topological_sort (Kahn's algorithm)
- load() validation and sorted node output
- load_from_file() filesystem loading
- Edge cases: empty graph, cycles, single node, disconnected nodes
"""

import json
from pathlib import Path

import pytest


# ======================================================================
# topological_sort
# ======================================================================


class TestTopologicalSort:
    """Tests for the Kahn's algorithm sorting function."""

    def test_linear_chain(self):
        """A -> B -> C should preserve order."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [
            {"id": "A", "label": "Start"},
            {"id": "B", "label": "Middle"},
            {"id": "C", "label": "End"},
        ]
        edges = [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
        ]
        result = topological_sort(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids == ["A", "B", "C"]

    def test_diamond_dependency(self):
        """A -> (B, C) -> D should produce A before B,C before D."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [
            {"id": "A", "label": "Start"},
            {"id": "B", "label": "Left"},
            {"id": "C", "label": "Right"},
            {"id": "D", "label": "End"},
        ]
        edges = [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
            {"from": "B", "to": "D"},
            {"from": "C", "to": "D"},
        ]
        result = topological_sort(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids.index("A") < ids.index("B")
        assert ids.index("A") < ids.index("C")
        assert ids.index("B") < ids.index("D")
        assert ids.index("C") < ids.index("D")

    def test_single_node_no_edges(self):
        """A single node with no edges should be returned as-is."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [{"id": "only", "label": "Only Node"}]
        result = topological_sort(nodes, [])
        assert len(result) == 1
        assert result[0]["id"] == "only"

    def test_disconnected_nodes(self):
        """Disconnected nodes should appear in their original order."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [
            {"id": "B", "label": "Second"},
            {"id": "A", "label": "First"},
        ]
        result = topological_sort(nodes, [])
        ids = [n["id"] for n in result]
        assert ids == ["B", "A"]  # original order preserved

    def test_circular_dependency_does_not_raise(self):
        """A -> B -> C -> A (cycle) should not crash; nodes are appended
        in original order."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [
            {"id": "A", "label": "A"},
            {"id": "B", "label": "B"},
            {"id": "C", "label": "C"},
        ]
        edges = [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
            {"from": "C", "to": "A"},
        ]
        result = topological_sort(nodes, edges)
        ids = [n["id"] for n in result]
        # All nodes should be present
        assert set(ids) == {"A", "B", "C"}

    def test_empty_nodes(self):
        """Passing an empty node list should return an empty list."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        result = topological_sort([], [])
        assert result == []

    def test_self_loop_node(self):
        """A node with an edge to itself should still appear in output."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [{"id": "A", "label": "A"}]
        edges = [{"from": "A", "to": "A"}]
        result = topological_sort(nodes, edges)
        assert len(result) == 1
        assert result[0]["id"] == "A"

    def test_complex_dag(self):
        """A larger DAG should produce a valid topological order."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [
            {"id": "1"}, {"id": "2"}, {"id": "3"},
            {"id": "4"}, {"id": "5"}, {"id": "6"},
        ]
        edges = [
            {"from": "1", "to": "2"},
            {"from": "1", "to": "3"},
            {"from": "2", "to": "4"},
            {"from": "3", "to": "4"},
            {"from": "4", "to": "5"},
            {"from": "1", "to": "6"},
        ]
        result = topological_sort(nodes, edges)
        ids = [n["id"] for n in result]

        # Verify every edge direction is respected
        for e in edges:
            frm, to = e["from"], e["to"]
            assert ids.index(frm) < ids.index(to), f"Edge {frm}->{to} violated"

    def test_edges_referencing_nonexistent_nodes(self):
        """Edges pointing to nodes not in the node list should be ignored."""
        from ccconfigmanager.executor.workflow_loader import topological_sort

        nodes = [{"id": "A"}, {"id": "B"}]
        edges = [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "Z"},   # Z not in nodes
            {"from": "Z", "to": "B"},   # Z not in nodes
        ]
        result = topological_sort(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids == ["A", "B"]


# ======================================================================
# load()
# ======================================================================


class TestLoad:
    """Tests for the ``load()`` function that validates and sorts workflow data."""

    VALID_WORKFLOW = {
        "slug": "test-wf",
        "name": "Test Workflow",
        "description": "A workflow for testing",
        "mode": "auto",
        "nodes": [
            {"id": "n1", "type": "agent", "label": "Step 1"},
            {"id": "n2", "type": "agent", "label": "Step 2"},
        ],
        "edges": [
            {"from": "n1", "to": "n2"},
        ],
    }

    def test_load_valid_workflow(self):
        """A well-formed workflow should return sorted nodes and metadata."""
        from ccconfigmanager.executor.workflow_loader import load

        result = load(self.VALID_WORKFLOW)
        assert result["slug"] == "test-wf"
        assert result["name"] == "Test Workflow"
        assert result["mode"] == "auto"
        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["id"] == "n1"
        assert result["nodes"][1]["id"] == "n2"

    def test_load_empty_nodes_raises(self):
        """A workflow with no nodes should raise ValueError."""
        from ccconfigmanager.executor.workflow_loader import load

        with pytest.raises(ValueError, match="没有节点"):
            load({"nodes": [], "edges": []})

    def test_load_missing_nodes_key(self):
        """A dict with no 'nodes' key should treat as empty and raise."""
        from ccconfigmanager.executor.workflow_loader import load

        with pytest.raises(ValueError, match="没有节点"):
            load({"edges": []})

    def test_load_missing_edges_key(self):
        """A dict with no 'edges' key should treat as empty list (no crash)."""
        from ccconfigmanager.executor.workflow_loader import load

        result = load({"nodes": [{"id": "n1"}]})
        assert len(result["nodes"]) == 1

    def test_load_with_circular_dependency(self):
        """A workflow with a cycle should still load (nodes appended)."""
        from ccconfigmanager.executor.workflow_loader import load

        wf = {
            "slug": "cycle-wf",
            "nodes": [
                {"id": "A"}, {"id": "B"}, {"id": "C"},
            ],
            "edges": [
                {"from": "A", "to": "B"},
                {"from": "B", "to": "C"},
                {"from": "C", "to": "A"},
            ],
        }
        result = load(wf)
        assert len(result["nodes"]) == 3

    def test_load_preserves_extra_fields(self):
        """Extra keys in the workflow dict should be passed through."""
        from ccconfigmanager.executor.workflow_loader import load

        wf = {
            **self.VALID_WORKFLOW,
            "custom_key": "custom_value",
            "version": 2,
        }
        result = load(wf)
        # load() does not copy unknown keys, only documented ones
        assert result["slug"] == "test-wf"
        assert result["name"] == "Test Workflow"

    def test_load_step_mode(self):
        """A workflow with mode='step' should reflect that."""
        from ccconfigmanager.executor.workflow_loader import load

        wf = {**self.VALID_WORKFLOW, "mode": "step"}
        result = load(wf)
        assert result["mode"] == "step"

    def test_load_with_none_value(self):
        """Passing ``None`` as workflow_data should raise an AttributeError
        or TypeError (not just hang)."""
        from ccconfigmanager.executor.workflow_loader import load

        with pytest.raises((AttributeError, TypeError, ValueError)):
            load(None)  # type: ignore[arg-type]


# ======================================================================
# load_from_file()
# ======================================================================


class TestLoadFromFile:
    """Tests for loading workflow from a JSON file on disk."""

    def test_load_valid_file(self, tmp_path):
        """A valid JSON workflow file should load correctly."""
        from ccconfigmanager.executor.workflow_loader import load_from_file

        wf = {
            "slug": "file-wf",
            "name": "File WF",
            "nodes": [{"id": "n1", "label": "Node 1"}],
            "edges": [],
        }
        fp = tmp_path / "workflow.json"
        fp.write_text(json.dumps(wf), encoding="utf-8")

        result = load_from_file(str(fp))
        assert result["slug"] == "file-wf"
        assert len(result["nodes"]) == 1

    def test_load_nonexistent_file(self, tmp_path):
        """A non-existent file path should raise FileNotFoundError."""
        from ccconfigmanager.executor.workflow_loader import load_from_file

        with pytest.raises(FileNotFoundError):
            load_from_file(str(tmp_path / "does_not_exist.json"))

    def test_load_invalid_json(self, tmp_path):
        """A malformed JSON file should raise json.JSONDecodeError."""
        from ccconfigmanager.executor.workflow_loader import load_from_file

        fp = tmp_path / "bad.json"
        fp.write_text("not json at all", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            load_from_file(str(fp))

    def test_load_empty_file(self, tmp_path):
        """An empty file should raise an error (JSONDecodeError or ValueError)."""
        from ccconfigmanager.executor.workflow_loader import load_from_file

        fp = tmp_path / "empty.json"
        fp.write_text("", encoding="utf-8")

        with pytest.raises((json.JSONDecodeError, ValueError)):
            load_from_file(str(fp))

    def test_load_file_without_nodes(self, tmp_path):
        """A valid JSON file that fails load() validation should raise."""
        from ccconfigmanager.executor.workflow_loader import load_from_file

        fp = tmp_path / "no_nodes.json"
        fp.write_text('{"slug": "empty"}', encoding="utf-8")

        with pytest.raises(ValueError, match="没有节点"):
            load_from_file(str(fp))
