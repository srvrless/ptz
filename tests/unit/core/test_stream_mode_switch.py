"""
Тесты переключения видеопотока при смене режима детектора (optical ↔ thermal).

Покрытие:
- Инициализация: камера подключается к правильному RTSP URL
- Runtime: camera.switch_url вызывается с корректным URL при смене режима
- Трекер сбрасывается при смене потока
- Детектор переключается на новую модель
- Camera.switch_url: изменяет URL, no-op, очистка кадра
- Full pipeline: кадры приходят с правильного потока
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, call, patch

from app.config.settings import CameraConfig, DetectorMode
from app.core.detection.yolo_detector import DetectorManager, ObjectDetector
from app.core.streaming.frame import ProcessFrame
from app.core.tracking.botsort_tracker import BOTSortTracker

OPTICAL_URL = "rtsp://192.168.1.100:554/optical"
THERMAL_URL = "rtsp://192.168.1.100:554/thermal_ik"
FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cam_cfg():
    return CameraConfig(
        id=1, name="Test Camera", host="192.168.1.100",
        user="admin", password="password", port=554,
        rtsp_url=OPTICAL_URL, rtsp_url_ik=THERMAL_URL,
        lat=55.75, lon=37.61, height=10.0, rate=0.0, ptz_type="onvif",
    )


@pytest.fixture
def mock_camera():
    cam = MagicMock()
    cam.switch_url = MagicMock()
    cam.current_url = OPTICAL_URL
    cam.get_frame.return_value = FRAME
    return cam


@pytest.fixture
def mock_auto_ptz():
    mgr = MagicMock()
    mgr.get_or_create.return_value = MagicMock()
    return mgr


@pytest.fixture
def make_pf(cam_cfg, mock_camera, mock_auto_ptz):
    """
    Factory fixture: создаёт ProcessFrame с нужным начальным режимом.

    Возвращает функцию (init_mode, camera=mock_camera) → (pf, dm, detector).
    """
    _sentinel = object()

    def factory(init_mode=DetectorMode.OPTICAL, *, camera=_sentinel):
        dm = MagicMock(spec=DetectorManager)
        det = MagicMock(spec=ObjectDetector)
        det.detect.return_value = []
        dm.get_detector.return_value = det
        dm.get_current_mode.return_value = init_mode

        pf = ProcessFrame(
            camera_id=1,
            auto_ptz=mock_auto_ptz,
            enable_auto_tracking=False,
            enable_detection=True,
            cam_cfg=cam_cfg,
            camera=mock_camera if camera is _sentinel else camera,
            detector_manager=dm,
        )
        return pf, dm, det

    return factory


@pytest.fixture
def real_camera():
    """Camera с замоканным cv2.VideoCapture."""
    with patch("app.core.camera.manager.cv2.VideoCapture") as mock_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cls.return_value = mock_cap

        from app.core.camera.manager import Camera
        from app.core.camera.models import CameraConnection

        camera = Camera(CameraConnection(url=OPTICAL_URL))
        yield camera, mock_cls


# ---------------------------------------------------------------------------
# Init: правильный RTSP URL при создании ProcessFrame
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode, expected_url", [
    (DetectorMode.OPTICAL, OPTICAL_URL),
    (DetectorMode.THERMAL, THERMAL_URL),
], ids=["optical", "thermal"])
def test_init_uses_correct_stream_url(make_pf, mock_camera, mode, expected_url):
    make_pf(init_mode=mode)
    mock_camera.switch_url.assert_called_once_with(expected_url)


def test_init_without_camera_backward_compat(make_pf):
    pf, _, _ = make_pf(camera=None)
    assert pf._cached_mode == DetectorMode.OPTICAL


# ---------------------------------------------------------------------------
# Runtime: переключение потока при смене режима
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("from_mode, to_mode, expected_url", [
    (DetectorMode.OPTICAL, DetectorMode.THERMAL, THERMAL_URL),
    (DetectorMode.THERMAL, DetectorMode.OPTICAL, OPTICAL_URL),
], ids=["optical→thermal", "thermal→optical"])
def test_runtime_switch_changes_stream_url(
    make_pf, mock_camera, from_mode, to_mode, expected_url,
):
    pf, dm, _ = make_pf(init_mode=from_mode)
    mock_camera.switch_url.reset_mock()

    dm.get_current_mode.return_value = to_mode
    pf.process_frame(FRAME)

    mock_camera.switch_url.assert_called_once_with(expected_url)


def test_no_switch_when_mode_unchanged(make_pf, mock_camera):
    pf, _, _ = make_pf()
    mock_camera.switch_url.reset_mock()

    for _ in range(10):
        pf.process_frame(FRAME)

    mock_camera.switch_url.assert_not_called()


def test_multiple_switches_correct_url_sequence(make_pf, mock_camera):
    pf, dm, _ = make_pf()
    mock_camera.switch_url.reset_mock()

    for mode in (DetectorMode.THERMAL, DetectorMode.OPTICAL, DetectorMode.THERMAL):
        dm.get_current_mode.return_value = mode
        pf.process_frame(FRAME)

    assert mock_camera.switch_url.call_args_list == [
        call(THERMAL_URL), call(OPTICAL_URL), call(THERMAL_URL),
    ]


# ---------------------------------------------------------------------------
# Tracker reset
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("do_switch, expect_reset", [
    (True, True),
    (False, False),
], ids=["mode_changed", "mode_same"])
def test_tracker_reset_depends_on_mode_change(make_pf, do_switch, expect_reset):
    pf, dm, _ = make_pf()
    pf.tracker = MagicMock(spec=BOTSortTracker)

    if do_switch:
        dm.get_current_mode.return_value = DetectorMode.THERMAL

    pf.process_frame(FRAME)

    if expect_reset:
        pf.tracker.reset.assert_called_once()
    else:
        pf.tracker.reset.assert_not_called()


# ---------------------------------------------------------------------------
# Detector integrity: новый детектор используется после переключения
# ---------------------------------------------------------------------------

def test_new_detector_used_after_switch(make_pf, mock_camera, mock_auto_ptz, cam_cfg):
    det_optical = MagicMock(spec=ObjectDetector, **{"detect.return_value": []})
    det_thermal = MagicMock(spec=ObjectDetector, **{"detect.return_value": []})

    dm = MagicMock(spec=DetectorManager)
    dm.get_current_mode.return_value = DetectorMode.OPTICAL
    dm.get_detector.return_value = det_optical

    pf = ProcessFrame(
        camera_id=1, auto_ptz=mock_auto_ptz,
        enable_auto_tracking=False, enable_detection=True,
        cam_cfg=cam_cfg, camera=mock_camera, detector_manager=dm,
    )

    pf.process_frame(FRAME)
    det_optical.detect.assert_called_once()

    dm.get_current_mode.return_value = DetectorMode.THERMAL
    dm.get_detector.return_value = det_thermal
    det_optical.detect.reset_mock()

    pf.process_frame(FRAME)
    det_thermal.detect.assert_called_once()
    det_optical.detect.assert_not_called()


# ---------------------------------------------------------------------------
# Camera.switch_url: низкоуровневые тесты
# ---------------------------------------------------------------------------

def test_switch_url_changes_connection(real_camera):
    camera, mock_cls = real_camera
    camera.switch_url(THERMAL_URL)

    assert camera.current_url == THERMAL_URL
    assert mock_cls.call_count == 2
    mock_cls.assert_called_with(THERMAL_URL)


def test_switch_url_noop_same_url(real_camera):
    camera, mock_cls = real_camera
    count_before = mock_cls.call_count
    camera.switch_url(OPTICAL_URL)

    assert mock_cls.call_count == count_before


def test_switch_url_clears_last_frame(real_camera):
    camera, _ = real_camera
    camera._last_frame = np.ones((480, 640, 3), dtype=np.uint8)
    camera.switch_url(THERMAL_URL)

    assert camera.get_frame() is None


# ---------------------------------------------------------------------------
# Full pipeline: кадры идут с правильного потока после переключения
# ---------------------------------------------------------------------------

def test_full_pipeline_stream_switch(cam_cfg, mock_auto_ptz):
    optical_frame = np.full((480, 640, 3), 100, dtype=np.uint8)
    thermal_frame = np.full((480, 640, 3), 200, dtype=np.uint8)

    det_opt = MagicMock(spec=ObjectDetector, **{"detect.return_value": []})
    det_thm = MagicMock(spec=ObjectDetector, **{"detect.return_value": []})

    dm = MagicMock(spec=DetectorManager)
    dm.get_current_mode.return_value = DetectorMode.OPTICAL
    dm.get_detector.return_value = det_opt

    camera = MagicMock()
    camera.current_url = OPTICAL_URL
    camera.get_frame.return_value = optical_frame

    def _switch(url):
        if url == THERMAL_URL:
            camera.get_frame.return_value = thermal_frame
        else:
            camera.get_frame.return_value = optical_frame
    camera.switch_url = MagicMock(side_effect=_switch)

    pf = ProcessFrame(
        camera_id=1, auto_ptz=mock_auto_ptz,
        enable_auto_tracking=False, enable_detection=True,
        cam_cfg=cam_cfg, camera=camera, detector_manager=dm,
    )

    # Optical phase
    pf.process_frame(camera.get_frame())
    assert np.array_equal(det_opt.detect.call_args[0][0], optical_frame)

    # Switch to thermal
    dm.get_current_mode.return_value = DetectorMode.THERMAL
    dm.get_detector.return_value = det_thm
    pf.process_frame(camera.get_frame())
    camera.switch_url.assert_called_with(THERMAL_URL)

    pf.process_frame(camera.get_frame())
    assert np.array_equal(det_thm.detect.call_args[0][0], thermal_frame)

    # Switch back to optical
    dm.get_current_mode.return_value = DetectorMode.OPTICAL
    dm.get_detector.return_value = det_opt
    det_opt.detect.reset_mock()
    pf.process_frame(camera.get_frame())
    camera.switch_url.assert_called_with(OPTICAL_URL)

    pf.process_frame(camera.get_frame())
    assert np.array_equal(det_opt.detect.call_args[0][0], optical_frame)
