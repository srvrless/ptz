from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config.settings import AppConfig, CameraConfig
from app.core.ptz.manager import PTZCameraManager
from app.exceptions import CameraNotFoundError, PTZMoveError
from app.services.camera_gateway_client import CameraGatewayClient
from app.services.camera_service import CameraService
from app.services.ptz_service import PTZService


def _cam_cfg(cam_id: int) -> CameraConfig:
    host = f"10.0.0.{cam_id}"
    return CameraConfig(
        id=cam_id,
        name=f"Camera {cam_id}",
        host=host,
        user="admin",
        password="pass",
        port=554,
        rtsp_url=f"rtsp://{host}/optical",
        rtsp_url_ik=f"rtsp://{host}/thermal",
        lat=55.0,
        lon=37.0,
        height=10.0,
        rate=0.0,
        ptz_type="onvif",
    )


@pytest.fixture
def config() -> AppConfig:
    # radar_id=1 -> heights[1] would IndexError; keep at least 2 items
    return AppConfig(heights=[0.0, 3.0], app_token="test-token-123")


@pytest.fixture
def ptz_manager() -> MagicMock:
    return MagicMock(spec=PTZCameraManager)


@pytest.fixture
def camera_gateway() -> MagicMock:
    return MagicMock(spec=CameraGatewayClient)


@pytest.fixture
def camera_service() -> MagicMock:
    svc = MagicMock(spec=CameraService)
    svc.touch_selected_camera = MagicMock()
    return svc


@pytest.fixture
def service(
    ptz_manager: MagicMock,
    config: AppConfig,
    camera_gateway: MagicMock,
    camera_service: MagicMock,
) -> PTZService:
    return PTZService(
        ptz_manager=ptz_manager,
        config=config,
        camera_gateway=camera_gateway,
        camera_service=camera_service,
    )


@pytest.mark.unit
class TestPTZServiceMoveToTargetWithExcludedCameras:
    def test_raises_camera_not_found_when_gateway_returns_none(
        self, service: PTZService, camera_gateway: MagicMock
    ) -> None:
        camera_gateway.get_nearest_camera_config.return_value = None

        with pytest.raises(CameraNotFoundError):
            service.move_to_target_with_excluded_cameras(
                client_id="c1",
                lat=55.0,
                lon=37.0,
                height=5.0,
                zoom=0.3,
                radar_id=1,
            )

    def test_moves_selected_nearest_camera_and_returns_camera_and_azimut(
        self,
        service: PTZService,
        ptz_manager: MagicMock,
        camera_gateway: MagicMock,
    ) -> None:
        camera_gateway.get_nearest_camera_config.return_value = _cam_cfg(7)
        ptz_manager.assert_owner = MagicMock()
        ptz_manager.get_controller.return_value = MagicMock()

        controller = MagicMock()
        controller.search_target.return_value = 12.34
        ptz_manager.get_controller.return_value = controller
        
        result = service.move_to_target_with_excluded_cameras(
            client_id="c1",
            lat=55.1,
            lon=37.1,
            height=6.0,
            zoom=0.5,
            radar_id=1,
            restart_before_move=True,
        )

        assert set(result.keys()) == {"camera", "azimut"}
        assert result["camera"].id == 7
        assert result["azimut"] == 12.34

        camera_gateway.get_nearest_camera_config.assert_called_once_with(
            lat=55.1, lon=37.1
        )
        controller.search_target.assert_called_once()

    def test_raises_ptz_move_error_when_controller_returns_none(
        self,
        service: PTZService,
        ptz_manager: MagicMock,
        camera_gateway: MagicMock,
    ) -> None:
        camera_gateway.get_nearest_camera_config.return_value = _cam_cfg(5)
        ptz_manager.assert_owner = MagicMock()
        controller = MagicMock()
        controller.search_target.return_value = None
        ptz_manager.get_controller.return_value = controller
        ptz_manager.restart_controller.return_value = controller

        with pytest.raises(PTZMoveError):
            service.move_to_target_with_excluded_cameras(
                client_id="c1",
                lat=55.1,
                lon=37.1,
                height=6.0,
                radar_id=1,
                restart_before_move=True,
            )
