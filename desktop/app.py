"""FastAPI application — serves dashboard and streams live metrics via WebSocket."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import asdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from specs import get_collector

# Resolve static files path (works in dev and PyInstaller bundle)
if hasattr(sys, "_MEIPASS"):
    STATIC_DIR = os.path.join(sys._MEIPASS, "static")
else:
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="PCSpecs", docs_url=None, redoc_url=None, openapi_url=None)

# CORS — only allow localhost origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Security headers
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
        "font-src 'self'; "
        "img-src 'self' data:"
    )
    return response

# Collector instance
collector = get_collector()


# --- Routes ---

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/specs")
async def get_specs():
    """One-time static hardware specs."""
    return collector.get_all_static()


# --- WebSocket ---

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        gone = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                gone.append(ws)
        for ws in gone:
            self.disconnect(ws)


manager = ConnectionManager()


@app.websocket("/ws/metrics")
async def websocket_metrics(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Keep connection alive; client can send "ping"
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                if msg == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                pass

            metrics = collector.get_live_metrics()
            await ws.send_json({
                "type": "metrics",
                "data": asdict(metrics),
            })
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


# Mount static files last (so explicit routes take priority)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
