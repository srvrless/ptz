from contextlib import contextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqladmin import Admin
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.admin import (
    CameraAdmin,
    CameraConnectionAdmin,
    CameraLocationAdmin,
    CameraPTZAdmin,
)
from app.api.v1.auto_ptz import router as auto_ptz_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.ptz import router as ptz_router
from app.api.v1.streams import router as streams_router
from app.container import create_container
from app.core.camera.manager import CameraManager
from app.db.base import engine
from app.services import CameraNotFoundError, PTZControllerNotFoundError, PTZMoveError
from logger.setup_logger import get_logger

logger = get_logger("app")


class DishkaMiddleware(BaseHTTPMiddleware):
    """Middleware для управления контекстом Dishka в sync режиме."""
    
    def __init__(self, app, container):
        super().__init__(app)
        self.container = container
    
    async def dispatch(self, request: Request, call_next):
        with self.container() as request_container:
            request.state.dishka_container = request_container
            response = await call_next(request)
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="PTZ Backend",
        version="1.0.0",
    )

    # Инициализируем БД
    init_database()
    
    # Создаём контейнер и добавляем middleware для sync режима
    container = create_container()
    app.add_middleware(DishkaMiddleware, container=container)
    app.state.dishka_container = container

    # Создаём и интегрируем контейнер dishka

    # Админка
    admin = Admin(app, engine, base_url="/admin", title="PTZ Admin")
    admin.add_view(CameraAdmin)
    admin.add_view(CameraConnectionAdmin)
    admin.add_view(CameraLocationAdmin)
    admin.add_view(CameraPTZAdmin)

    # Роутеры
    app.include_router(cameras_router)
    app.include_router(streams_router)
    app.include_router(ptz_router)
    app.include_router(auto_ptz_router)

    # Обработчики ошибок
    register_exception_handlers(app)

    @app.on_event("shutdown")
    async def shutdown_event():
        """
        Останавливаем все камеры при завершении приложения.
        Получаем CameraManager из контейнера dishka.
        """
        logger.info("Остановка всех камер...")
        with container() as request_container:
            camera_manager = await request_container.get(CameraManager)
            camera_manager.stop_all()
        
        # Закрываем контейнер
        await container.close()

    return app


def init_database() -> None:
    """
    Инициализирует БД: создаёт таблицы и загружает начальные данные.
    """
    try:
        from app.db.base import create_db_and_tables
        from app.db.session import Session
        from app.models.ptz_types import PTZType

        # Создаём все таблицы
        create_db_and_tables()

        # Проверяем и инициализируем справочник PTZ типов, если пуст
        db_session = Session()
        try:
            ptz_types_count = db_session.query(PTZType).count()
            if ptz_types_count == 0:
                logger.info("Initializing PTZ types...")
                default_types = [
                    PTZType(type="onvif"),
                    PTZType(type="tms20"),
                ]
                db_session.add_all(default_types)
                db_session.commit()
                logger.info("✅ PTZ types initialized")
        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


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
