"""
Тесты жизненного цикла select_camera / stop_selected_camera.

Покрытие:
- Старый воркер останавливается при выборе другой камеры
- Старая камера освобождается из CameraManager
- Повторный выбор той же камеры — noop
- Состояние сервиса сохраняется (APP scope)
- Репродукция бага: REQUEST scope теряет ссылку на воркер
- Стресс: быстрое переключение нескольких камер
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.exceptions import HTTPException

from app.config.settings import AppConfig, CameraConfig, DetectorMode
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.core.ptz.manager import PTZCameraManager
from app.services.camera_gateway_client import CameraGatewayClient
from app.services.camera_service import CameraService


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _cam_cfg(cam_id: int, *, client_id: str) -> CameraConfig:
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
        client_id=client_id,
        is_busy=True,
    )


@pytest.fixture
def camera_manager():
    mgr = MagicMock(spec=CameraManager)
    cam = MagicMock()
    cam.switch_url = MagicMock()
    mgr.get_or_create.return_value = cam
    return mgr


@pytest.fixture
def detector_manager():
    mgr = MagicMock(spec=DetectorManager)
    mgr.get_current_mode.return_value = DetectorMode.OPTICAL
    return mgr


@pytest.fixture
def service(camera_manager, detector_manager):
    """CameraService с замоканными зависимостями и авто-конфигом камер."""
    camera_gateway = MagicMock(spec=CameraGatewayClient)
    camera_gateway.claim_camera.side_effect = lambda camera_id, client_id: _cam_cfg(
        camera_id, client_id=client_id
    )
    camera_gateway.release_camera = MagicMock()
    svc = CameraService(
        camera_manager=camera_manager,
        ptz_manager=MagicMock(spec=PTZCameraManager),
        auto_ptz_manager=MagicMock(spec=AutoPTZManager),
        detector_manager=detector_manager,
        config=MagicMock(spec=AppConfig),
        camera_gateway=camera_gateway,
    )
    return svc


def _make_service(camera_manager, detector_manager):
    """Фабрика для создания независимых экземпляров CameraService."""
    camera_gateway = MagicMock(spec=CameraGatewayClient)
    camera_gateway.claim_camera.side_effect = lambda camera_id, client_id: _cam_cfg(
        camera_id, client_id=client_id
    )
    camera_gateway.release_camera = MagicMock()
    svc = CameraService(
        camera_manager=camera_manager,
        ptz_manager=MagicMock(spec=PTZCameraManager),
        auto_ptz_manager=MagicMock(spec=AutoPTZManager),
        detector_manager=detector_manager,
        config=MagicMock(spec=AppConfig),
        camera_gateway=camera_gateway,
    )
    return svc


# ---------------------------------------------------------------------------
# Stop event lifecycle
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
class TestStopEventLifecycle:
    def test_old_stop_event_set_on_camera_switch(self, _sock_factory, _, service):
        client_id = "c1"
        service.select_camera(camera_id=1, client_id=client_id)
        event_1 = service._sessions[client_id].stop_event
        assert not event_1.is_set()

        service.select_camera(camera_id=2, client_id=client_id)
        assert event_1.is_set()

    def test_new_event_created_for_each_camera(self, _sock_factory, _, service):
        client_id = "c1"
        service.select_camera(camera_id=1, client_id=client_id)
        event_1 = service._sessions[client_id].stop_event

        service.select_camera(camera_id=2, client_id=client_id)
        event_2 = service._sessions[client_id].stop_event

        assert event_1 is not event_2
        assert not event_2.is_set()


# ---------------------------------------------------------------------------
# Camera release
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
class TestCameraRelease:
    @pytest.mark.parametrize(
        "cam_ids, expect_release_id",
        [
            ([1, 2], 1),
        ],
        ids=["switch_releases_old"],
    )
    def test_old_camera_released_on_switch(
        self,
        _sock_factory,
        _,
        service,
        camera_manager,
        cam_ids,
        expect_release_id,
    ):
        client_id = "c1"
        for cid in cam_ids:
            service.select_camera(camera_id=cid, client_id=client_id)
        camera_manager.release.assert_called_once_with(expect_release_id)

    def test_same_camera_not_released(self, _sock_factory, _, service, camera_manager):
        client_id = "c1"
        service.select_camera(camera_id=1, client_id=client_id)
        # имитируем "воркер не жив" в текущей сессии
        service._sessions[client_id].worker_thread = MagicMock(
            is_alive=MagicMock(return_value=False)
        )
        service.select_camera(camera_id=1, client_id=client_id)

        camera_manager.release.assert_not_called()


# ---------------------------------------------------------------------------
# Noop on same camera
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
def test_same_camera_alive_worker_noop(_sock_factory, mock_sender, service):
    mock_sender.side_effect = lambda **kw: kw["stop_event"].wait()

    client_id = "c1"
    service.select_camera(camera_id=1, client_id=client_id)
    first_thread = service._sessions[client_id].worker_thread
    assert first_thread.is_alive()

    service.select_camera(camera_id=1, client_id=client_id)
    assert service._sessions[client_id].worker_thread is first_thread

    service.stop_selected_camera(client_id)


# ---------------------------------------------------------------------------
# stop_selected_camera
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
def test_stop_sets_event_and_clears_state(_sock_factory, _, service, camera_manager):
    client_id = "c1"
    service.select_camera(camera_id=1, client_id=client_id)
    stop_event = service._sessions[client_id].stop_event

    service.stop_selected_camera(client_id)

    assert stop_event.is_set()
    camera_manager.release.assert_called_once_with(1)
    assert service.get_selected_camera_id(client_id) is None
    assert client_id not in service._sessions


# ---------------------------------------------------------------------------
# State preserved across calls (APP scope vs REQUEST scope)
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
class TestScopeIntegrity:
    def test_single_instance_preserves_state(self, _sock_factory, _, service):
        client_id = "c1"
        events = []
        for cam_id in [1, 2, 3]:
            service.select_camera(camera_id=cam_id, client_id=client_id)
            events.append(service._sessions[client_id].stop_event)

        assert all(e.is_set() for e in events[:-1])
        assert not events[-1].is_set()
        assert service.get_selected_camera_id(client_id) == 3

    @pytest.mark.parametrize(
        "same_instance, old_event_should_be_set",
        [
            (True, True),
            (False, False),
        ],
        ids=["APP_scope", "REQUEST_scope_bug"],
    )
    def test_scope_affects_worker_lifecycle(
        self,
        _sock_factory,
        _,
        camera_manager,
        detector_manager,
        same_instance,
        old_event_should_be_set,
    ):
        svc1 = _make_service(camera_manager, detector_manager)
        client_id = "c1"
        svc1.select_camera(camera_id=1, client_id=client_id)
        orphaned_event = svc1._sessions[client_id].stop_event

        svc2 = (
            svc1 if same_instance else _make_service(camera_manager, detector_manager)
        )
        svc2.select_camera(camera_id=2, client_id=client_id)

        assert orphaned_event.is_set() == old_event_should_be_set


# ---------------------------------------------------------------------------
# Stress: rapid camera switches
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Я В РОТ ВЫЕБУ КТО УДАЛИТ ЭТИ ТЕСТЫ, ЛИЧНО Я НАЙДУ ТЕБЯ КТО УДАЛИТ
# ДАЖЕ В БЕССРОЧНОМ ОТПУСКЕ
# ---------------------------------------------------------------------------
@patch("app.services.camera_service.run_detection_sender")
@patch("app.services.camera_service._default_connection_factory")
def test_rapid_switches_all_old_events_set(_sock_factory, _, service):
    client_id = "c1"
    events = []
    for cam_id in range(1, 6):
        service.select_camera(camera_id=cam_id, client_id=client_id)
        events.append(service._sessions[client_id].stop_event)

    for i, ev in enumerate(events[:-1]):
        assert ev.is_set(), f"Event от камеры {i + 1} должен быть set"

        assert not events[-1].is_set()
    assert service.get_selected_camera_id(client_id) == 5


@patch("app.services.camera_service._default_connection_factory")
def test_success_select_camera_create_controller(_sock_factory, service):
    client_id = "c1"
    cam_id = 1

    service.ptz_manager.is_initialized.return_value = True
    service.select_camera(camera_id=cam_id, client_id=client_id)
    assert service.ptz_manager.is_initialized(cam_id)


@patch("app.services.camera_service._default_connection_factory")
def test_failed_select_camera_create_controller(_sock_factory, service):
    client_id = "c1"
    cam_id = 1

    _sock_factory.side_effect = Exception("Connection refused")
    service.ptz_manager.is_initialized.return_value = False
    with pytest.raises(Exception, match="Не удалось подключиться к сервису стриминга"):
        service.select_camera(camera_id=cam_id, client_id=client_id)

    assert not service.ptz_manager.is_initialized(cam_id)


@patch("app.services.camera_service._default_connection_factory")
def test_failed_select_camera_create_controller_rollback(_sock_factory, service):
    cam_id = 1
    client_id = "c1"
    service.ptz_manager.is_initialized.return_value = True
    service.select_camera(camera_id=cam_id, client_id=client_id)
    assert service.ptz_manager.is_initialized(cam_id)
    _sock_factory.side_effect = Exception("Connection refused")
    service.ptz_manager.is_initialized.return_value = False
    with pytest.raises(Exception, match="Не удалось подключиться к сервису стриминга"):
        service.select_camera(camera_id=cam_id, client_id=client_id)
    assert not service.ptz_manager.is_initialized(cam_id)
    assert service.ptz_manager.clear_owner.called
    assert service.ptz_manager.clear_owner.call_args[0] == (cam_id, client_id)
    assert service.ptz_manager.clear_owner.call_args[0][0] == cam_id
    assert service.ptz_manager.clear_owner.call_args[0][1] == client_id
