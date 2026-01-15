# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config.settings import config
from app.api.v1.cameras import router as cameras_router
from app.api.v1.streams import router as streams_router
from app.api.v1.ptz import router as ptz_router
from app.api.v1.auto_ptz import router as auto_ptz_router
from app.services import (
    CameraNotFoundError,
    PTZControllerNotFoundError,
    PTZMoveError,
)
from app.core.camera.manager import camera_manager
from logger.setup_logger import get_logger

logger = get_logger("app")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PTZ Backend",
        version="1.0.0",
    )

    # Роутеры
    app.include_router(cameras_router)
    app.include_router(streams_router)
    app.include_router(ptz_router)
    app.include_router(auto_ptz_router)

    # Обработчики ошибок
    register_exception_handlers(app)

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Остановка всех камер...")
        camera_manager.stop_all()

    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CameraNotFoundError)
    async def camera_not_found_handler(request: Request, exc: CameraNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "camera_not_found", "message": str(exc)},
        )

    @app.exception_handler(PTZControllerNotFoundError)
    async def ptz_not_found_handler(request: Request, exc: PTZControllerNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "ptz_controller_not_found", "message": str(exc)},
        )

    @app.exception_handler(PTZMoveError)
    async def ptz_move_error_handler(request: Request, exc: PTZMoveError):
        return JSONResponse(
            status_code=500,
            content={"error": "ptz_move_failed", "message": str(exc)},
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": str(exc)},
        )

app = create_app()

# Для запуска: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
