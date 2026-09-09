"""
CaseFill-AI — FastAPI Application
Document intake assistant for Orphan Family Support Program (OFSP).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import UPLOADS_DIR
from .db import init_db
from .routers import auth, cases, admin, chat, stats


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="CaseFill-AI",
        description="Document intake assistant for Orphan Family Support Program (OFSP)",
        version="2.0.0",
    )

    # CORS — allow React dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize database
    init_db()

    # Mount uploads directory for serving images
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

    # Register routers
    app.include_router(auth.router)
    app.include_router(cases.router)
    app.include_router(admin.router)
    app.include_router(chat.router)
    app.include_router(stats.router)

    # Health check
    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "CaseFill-AI"}

    # Serve frontend SPA in production
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend-assets")

        @app.get("/")
        async def serve_root():
            """Serve index.html at the root path."""
            return FileResponse(frontend_dist / "index.html")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the React SPA for any non-API route."""
            # Try exact file first (e.g. favicon.svg)
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            # Fall back to index.html for client-side routing
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
