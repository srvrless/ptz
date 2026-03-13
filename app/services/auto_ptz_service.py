from __future__ import annotations

from typing import Optional

from app.config.settings import CameraConfig
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.exceptions import CameraNotFoundError
from app.services.camera_gateway_client import CameraGatewayClient


class AutoPTZService:
    """
    Сервис автослежения PTZ.
    Логика разрешения конфига (кэш vs БД) — здесь, не в эндпоинтах.
    """

    def __init__(
        self,
        auto_ptz_manager: AutoPTZManager,
        ptz_manager: PTZCameraManager,
        camera_gateway: CameraGatewayClient,
    ) -> None:
        self._auto_ptz_manager = auto_ptz_manager
        self._ptz_manager = ptz_manager
        self._camera_gateway = camera_gateway

    def _assert_owned(self, camera_id: int, client_id: str) -> None:
        """
        Проверяем локальный ownership камеры.
        Auto‑tracking разрешён только для владельца, выбранного через select_camera.
        """
        self._ptz_manager.assert_owner(camera_id, client_id)

    def _resolve_camera_config(self, camera_id: int) -> CameraConfig:
        """Из кэша PTZManager, если камера инициализирована; иначе запрос в БД."""
        if self._ptz_manager.is_initialized(camera_id):
            return self._ptz_manager.get_cached_config(camera_id)
        return self._fetch_camera_config_from_api(camera_id)

    def _fetch_camera_config_from_api(self, camera_id: int) -> CameraConfig:
        camera_cfg = self._camera_gateway.get_camera_config_by_id(camera_id)
        if camera_cfg is None:
            raise CameraNotFoundError(str(camera_id))
        return camera_cfg

    def set_target(
        self,
        camera_id: int,
        track_id: Optional[int],
        *,
        client_id: str,
    ) -> None:
        self._assert_owned(camera_id, client_id)
        cam_cfg = self._resolve_camera_config(camera_id)
        self._auto_ptz_manager.set_target(camera_id, track_id, cam_cfg)

    def clear_target(self, camera_id: int, *, client_id: str) -> None:
        self._assert_owned(camera_id, client_id)
        cam_cfg = self._resolve_camera_config(camera_id)
        self._auto_ptz_manager.clear_target(camera_id, cam_cfg)

    def get_target(self, camera_id: int, *, client_id: str) -> Optional[int]:
        self._assert_owned(camera_id, client_id)
        cam_cfg = self._resolve_camera_config(camera_id)
        return self._auto_ptz_manager.get_target(camera_id, cam_cfg)
