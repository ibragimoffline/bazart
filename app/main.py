import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.request_context import RequestIdMiddleware
from app.realtime import manager
from app.services.auction_closer import start_auction_closer, stop_auction_closer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ilova hayotiy sikli: fon worker'larni ishga tushiradi va to'xtatadi.

    Worker'lar faqat yoqilgan va test bo'lmagan muhitda ishga tushadi
    (guard start_* ichida). Shutdown'da task'lar bekor qilinadi.
    """
    # WS manager'ga event loop'ni beramiz — sync bid oqimi broadcast'ni
    # shu loop'ga rejalashtira olishi uchun (broadcast_threadsafe).
    manager.set_loop(asyncio.get_running_loop())
    closer_task = start_auction_closer()
    try:
        yield
    finally:
        await stop_auction_closer(closer_task)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    # CORS: frontend (Next.js) brauzerdan /api/v1 ga so'rov yuboradi.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix="/api/v1")
    Path(settings.local_upload_dir).mkdir(parents=True, exist_ok=True)
    app.mount(
        settings.public_upload_url_prefix,
        StaticFiles(directory=settings.local_upload_dir),
        name="uploads",
    )
    return app


app = create_app()
