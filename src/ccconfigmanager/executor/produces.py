"""Produces validator — checks that declared output files exist."""

from pathlib import Path


def check(produces: list[str], project_path: str) -> list[dict]:
    """Check if declared produce files exist. Returns list of {name, exists, path}."""
    results = []
    for filename in produces:
        fp = Path(project_path) / filename
        exists = fp.is_file()
        size = 0
        if exists:
            try:
                size = fp.stat().st_size
            except OSError:
                pass
        results.append({
            "name": filename,
            "exists": exists,
            "path": str(fp),
            "size": size,
        })
    return results


def all_exist(produces: list[str], project_path: str) -> bool:
    results = check(produces, project_path)
    return all(r["exists"] for r in results)
