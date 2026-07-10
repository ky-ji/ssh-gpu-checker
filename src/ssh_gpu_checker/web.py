from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ssh_gpu_checker.coordinator import ScanCoordinator


def create_app(coordinator: ScanCoordinator) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        coordinator.start()
        try:
            yield
        finally:
            coordinator.stop()

    app = FastAPI(
        title="SSH GPU Dashboard",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    static_dir = Path(__file__).with_name("static")
    app.mount(
        "/static",
        StaticFiles(directory=static_dir, check_dir=False),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    async def dashboard() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/api/v1/snapshot")
    async def snapshot():
        coordinator.touch_client()
        return coordinator.snapshot()

    @app.post("/api/v1/refresh", status_code=202)
    async def refresh(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            return JSONResponse(
                {"detail": "Content-Type must be application/json"},
                status_code=415,
            )
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"detail": "Invalid JSON"}, status_code=400)
        if not isinstance(payload, dict):
            return JSONResponse(
                {"detail": "JSON body must be an object"}, status_code=400
            )
        coordinator.request_refresh()
        return JSONResponse({"accepted": True}, status_code=202)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app
