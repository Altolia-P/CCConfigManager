"""CCConfigManager — FastAPI application entry point."""

import mimetypes
import os
import webbrowser

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .registry import get_static_dir

# Ensure correct MIME types on Windows
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

STATIC_DIR = get_static_dir()

app = FastAPI(title="CCConfigManager")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
from .routes import items, proj, packs as pack_routes, workflows, runs, agents

app.include_router(items.router)
app.include_router(proj.router)
app.include_router(pack_routes.router)
app.include_router(workflows.router)
app.include_router(runs.router)
app.include_router(agents.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main():
    import uvicorn
    try:
        port = int(os.environ.get("PORT", 8900))
    except (ValueError, TypeError):
        port = 8900
    url = f"http://127.0.0.1:{port}"
    print(f"CCConfigManager → {url}")
    webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
