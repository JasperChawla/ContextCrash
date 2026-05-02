from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analytics, results, runs

app = FastAPI(
    title="ContextCrash API",
    description="LLM reliability benchmarking for RAG pipelines",
    version="0.1.0",
)

# Allow the React dev server to call this API without proxy fiddling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(results.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "contextcrash"}


@app.get("/")
def root():
    return {
        "name": "ContextCrash API",
        "version": "0.1.0",
        "docs": "/docs",
    }
