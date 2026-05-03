from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import analytics, results, runs

app = FastAPI(
    title="ContextCrash API",
    description="LLM reliability benchmarking for RAG pipelines",
    version="0.1.0",
)

# Allow the React dev server to call this API without proxy fiddling.
# In production the frontend is served from the same origin, so CORS is only
# needed for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes (must be registered before the SPA catch-all) ──────────────────
app.include_router(runs.router)
app.include_router(results.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "contextcrash"}


# ── Frontend static files ─────────────────────────────────────────────────────
# Only mounted when the React build exists (production / Docker).
# In local dev the Vite dev server runs separately on port 3000.
_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _DIST.is_dir():
    # Serve hashed JS/CSS/image assets at /assets/...
    _assets = _DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    # Catch-all: return index.html for every path that hasn't matched an API
    # route above, so React Router can handle client-side navigation.
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):  # noqa: ARG001
        return FileResponse(str(_DIST / "index.html"))
