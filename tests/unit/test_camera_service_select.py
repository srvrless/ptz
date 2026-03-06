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

from app.config.settings import AppConfig, CameraConfig, DetectorMode
from app.core.camera.manager import CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.services.camera_service import CameraService


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


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
    svc = CameraService(
        camera_manager=camera_manager,
        auto_ptz_manager=MagicMock(spec=AutoPTZManager),
        detector_manager=detector_manager,
        config=MagicMock(spec=AppConfig),
    )
    svc.get_camera_config = MagicMock(side_effect=lambda u, cid: _cam_cfg(cid))
    return svc


@pytest.fixture
def uow():
    return MagicMock()


def _make_service(camera_manager, detector_manager):
    """Фабрика для создания независимых экземпляров CameraService."""
    svc = CameraService(
        camera_manager=camera_manager,
        auto_ptz_manager=MagicMock(spec=AutoPTZManager),
        detector_manager=detector_manager,
        config=MagicMock(spec=AppConfig),
    )
    svc.get_camera_config = MagicMock(side_effect=lambda u, cid: _cam_cfg(cid))
    return svc


# ---------------------------------------------------------------------------
# Stop event lifecycle
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
class TestStopEventLifecycle:
    def test_old_stop_event_set_on_camera_switch(self, _, service, uow):
        service.select_camera(uow, camera_id=1)
        event_1 = service._stop_event
        assert not event_1.is_set()

        service.select_camera(uow, camera_id=2)
        assert event_1.is_set()

    def test_new_event_created_for_each_camera(self, _, service, uow):
        service.select_camera(uow, camera_id=1)
        event_1 = service._stop_event

        service.select_camera(uow, camera_id=2)
        event_2 = service._stop_event

        assert event_1 is not event_2
        assert not event_2.is_set()


# ---------------------------------------------------------------------------
# Camera release
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
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
        _,
        service,
        uow,
        camera_manager,
        cam_ids,
        expect_release_id,
    ):
        for cid in cam_ids:
            service.select_camera(uow, camera_id=cid)
        camera_manager.release.assert_called_once_with(expect_release_id)

    def test_same_camera_not_released(self, _, service, uow, camera_manager):
        service.select_camera(uow, camera_id=1)
        service._worker_thread = MagicMock(is_alive=MagicMock(return_value=False))
        service.select_camera(uow, camera_id=1)

        camera_manager.release.assert_not_called()


# ---------------------------------------------------------------------------
# Noop on same camera
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
def test_same_camera_alive_worker_noop(mock_sender, service, uow):
    mock_sender.side_effect = lambda **kw: kw["stop_event"].wait()

    service.select_camera(uow, camera_id=1)
    first_thread = service._worker_thread
    assert first_thread.is_alive()

    service.select_camera(uow, camera_id=1)
    assert service._worker_thread is first_thread

    service.stop_selected_camera()


# ---------------------------------------------------------------------------
# stop_selected_camera
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
def test_stop_sets_event_and_clears_state(_, service, uow, camera_manager):
    service.select_camera(uow, camera_id=1)
    stop_event = service._stop_event

    service.stop_selected_camera()

    assert stop_event.is_set()
    camera_manager.release.assert_called_once_with(1)
    assert service._selected_camera_id is None
    assert service._worker_thread is None


# ---------------------------------------------------------------------------
# State preserved across calls (APP scope vs REQUEST scope)
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
class TestScopeIntegrity:
    def test_single_instance_preserves_state(self, _, service, uow):
        events = []
        for cam_id in [1, 2, 3]:
            service.select_camera(uow, camera_id=cam_id)
            events.append(service._stop_event)

        assert all(e.is_set() for e in events[:-1])
        assert not events[-1].is_set()
        assert service._selected_camera_id == 3

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
        _,
        uow,
        camera_manager,
        detector_manager,
        same_instance,
        old_event_should_be_set,
    ):
        svc1 = _make_service(camera_manager, detector_manager)
        svc1.select_camera(uow, camera_id=1)
        orphaned_event = svc1._stop_event

        svc2 = (
            svc1 if same_instance else _make_service(camera_manager, detector_manager)
        )
        svc2.select_camera(uow, camera_id=2)

        assert orphaned_event.is_set() == old_event_should_be_set


# ---------------------------------------------------------------------------
# Stress: rapid camera switches
# ---------------------------------------------------------------------------


@patch("app.services.camera_service.run_detection_sender")
def test_rapid_switches_all_old_events_set(_, service, uow):
    events = []
    for cam_id in range(1, 6):
        service.select_camera(uow, camera_id=cam_id)
        events.append(service._stop_event)

    for i, ev in enumerate(events[:-1]):
        assert ev.is_set(), f"Event от камеры {i + 1} должен быть set"

    assert not events[-1].is_set()
    assert service._selected_camera_id == 5
