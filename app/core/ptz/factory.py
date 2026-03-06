from __future__ import annotations

from typing import Dict, Optional, Type, TYPE_CHECKING

from app.config.settings import CameraConfig
from logger.setup_logger import get_logger

if TYPE_CHECKING:
    from app.core.ptz.base import BasePTZController

logger = get_logger("ptz_factory")


class PTZControllerFactory:
    """
    Фабрика для создания PTZ-контроллеров.
    Контроллеры регистрируются через декоратор @register.
    """

    _registry: Dict[str, Type["BasePTZController"]] = {}

    @classmethod
    def register(cls, ptz_type: str):
        """
        Декоратор для регистрации контроллера.

        Использование:
            @PTZControllerFactory.register("onvif")
            class PTZController(BasePTZController):
                ...
        """

        def decorator(controller_cls: Type["BasePTZController"]):
            cls._registry[ptz_type.lower()] = controller_cls
            logger.info(
                f"Registered PTZ controller: {ptz_type} -> {controller_cls.__name__}"
            )
            return controller_cls

        return decorator

    @classmethod
    def create(
        cls, ptz_type: str, config: CameraConfig
    ) -> Optional["BasePTZController"]:
        """
        Создать контроллер по типу и конфигу камеры.
        """
        controller_cls = cls._registry.get(ptz_type.lower())

        if controller_cls is None:
            logger.error(
                f"Unknown PTZ type: {ptz_type}. Available: {list(cls._registry.keys())}"
            )
            return None

        return controller_cls.from_config(config)

    @classmethod
    def get_available_types(cls) -> list[str]:
        """Список зарегистрированных типов."""
        return list(cls._registry.keys())
