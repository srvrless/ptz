from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.v1.auto_ptz import router as auto_ptz_router
from app.api.v1.detector import router as detector_router
from app.api.v1.ptz import router as ptz_router
from app.api.v1.streams import router as streams_router
from app.container import create_container
from app.core.camera.manager import CameraManager
from app.exceptions import CameraNotFoundError, PTZControllerNotFoundError, PTZMoveError
from app.services.camera_service import CameraService
from logger.setup_logger import get_logger

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("✅ Application startup complete")

    yield

    container = app.state.container
    with container() as request_container:
        camera_service = request_container.get(CameraService)
        camera_manager = request_container.get(CameraManager)
        logger.info("Остановка активных TTL-сессий...")
        camera_service.stop_all_sessions()
        logger.info("Остановка всех камер...")
        camera_manager.stop_all()


def create_app() -> FastAPI:
    """Создает и конфигурирует FastAPI приложение."""
    app = FastAPI(title="PTZ Backend", version="1.0.0", lifespan=lifespan)
    container = create_container()
    setup_dishka(container, app)

    app.state.container = container
    logger.info("✅ Dishka container initialized")

    # Роутеры
    app.include_router(streams_router)
    app.include_router(ptz_router)
    app.include_router(auto_ptz_router)
    app.include_router(detector_router)

    # Обработчики ошибок
    register_exception_handlers(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует обработчики ошибок."""

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


# Создаём экземпляр приложения
app = create_app()

# Для запуска: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
