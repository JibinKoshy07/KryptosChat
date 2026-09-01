"""FastAPI application entrypoint.

Run with::
    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.services.presence import get_redis as presence_redis
from app.websocket.chat import handle_chat
from app.websocket.connection import manager
from app.websocket.presence import handle_presence

setup_logging(settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Redis pub/sub fanout so multi-instance deployments receive events.
    try:
        rc = presence_redis()
        await manager.start(rc)
        logger.info("event_listener_started", extra={"extra_fields": {}})
    except Exception:
        logger.warning("event_listener_failed", extra={"extra_fields": {}})
    yield
    try:
        await manager.stop()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Security headers.
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        return response

    # Structured error handling for application exceptions.
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "detail": exc.detail}},
        )

    # Generic fallback handler (never leak internals).
    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", extra={"extra_fields": {"path": request.url.path}}, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "detail": "Internal server error"}},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # --- WebSocket routes -------------------------------------------------
    @app.websocket("/ws/chat/{conversation_id}")
    async def ws_chat(websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        rc = presence_redis()
        try:
            await handle_chat(websocket, conversation_id, async_session_factory, rc)
        except WebSocketDisconnect:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    @app.websocket("/ws/presence")
    async def ws_presence(websocket: WebSocket):
        await websocket.accept()
        rc = presence_redis()
        try:
            await handle_presence(websocket, rc, async_session_factory)
        except WebSocketDisconnect:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    @app.get("/")
    async def root():
        return {"app": settings.app_name, "docs": "/api/docs"}

    return app


app = create_app()