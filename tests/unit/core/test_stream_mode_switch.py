"""
Тесты переключения видеопотока при смене режима детектора (optical ↔ thermal).

Проверяет, что:
- При инициализации камера подключается к правильному RTSP URL
- При runtime-переключении режима camera.switch_url вызывается с корректным URL
- Трекер сбрасывается при смене потока
- process_frame использует кадры с нового потока после переключения
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call, PropertyMock

from app.config.settings import CameraConfig, DetectorMode
from app.core.detection.yolo_detector import DetectorManager, ObjectDetector, Detection
from app.core.streaming.frame import ProcessFrame
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.core.tracking.centroid_tracker import CentroidTracker


OPTICAL_URL = "rtsp://192.168.1.100:554/optical"
THERMAL_URL = "rtsp://192.168.1.100:554/thermal_ik"


@pytest.fixture
def cam_cfg():
    return CameraConfig(
        id=1,
        name="Test Camera",
        host="192.168.1.100",
        user="admin",
        password="password",
        port=554,
        rtsp_url=OPTICAL_URL,
        rtsp_url_ik=THERMAL_URL,
        lat=55.75,
        lon=37.61,
        height=10.0,
        rate=0.0,
        ptz_type="onvif",
    )


@pytest.fixture
def mock_camera():
    camera = MagicMock()
    camera.switch_url = MagicMock()
    camera.current_url = OPTICAL_URL
    camera.get_frame.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
    return camera


@pytest.fixture
def mock_detector():
    detector = MagicMock(spec=ObjectDetector)
    detector.detect.return_value = []
    return detector


@pytest.fixture
def mock_detector_manager(mock_detector):
    manager = MagicMock(spec=DetectorManager)
    manager.get_detector.return_value = mock_detector
    manager.get_current_mode.return_value = DetectorMode.OPTICAL
    return manager


@pytest.fixture
def mock_auto_ptz_manager():
    manager = MagicMock(spec=AutoPTZManager)
    manager.get_or_create.return_value = MagicMock()
    return manager


def _make_process_frame(
    cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
):
    """Хелпер для создания ProcessFrame с моками."""
    return ProcessFrame(
        camera_id=1,
        auto_ptz_manager=mock_auto_ptz_manager,
        enable_auto_tracking=False,
        enable_detection=True,
        cam_cfg=cam_cfg,
        camera=mock_camera,
        detector_manager=mock_detector_manager,
    )


class TestInitStreamUrl:
    """Проверяет, что при инициализации камера подключается к правильному потоку."""

    def test_init_optical_mode_uses_optical_url(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL

        _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )

        mock_camera.switch_url.assert_called_once_with(OPTICAL_URL)

    def test_init_thermal_mode_uses_ik_url(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL

        _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )

        mock_camera.switch_url.assert_called_once_with(THERMAL_URL)

    def test_init_without_camera_does_not_crash(
        self, cam_cfg, mock_detector_manager, mock_auto_ptz_manager
    ):
        """ProcessFrame без camera (backward compat) не падает."""
        pf = ProcessFrame(
            camera_id=1,
            auto_ptz_manager=mock_auto_ptz_manager,
            enable_auto_tracking=False,
            enable_detection=True,
            cam_cfg=cam_cfg,
            camera=None,
            detector_manager=mock_detector_manager,
        )
        assert pf._cached_mode == DetectorMode.OPTICAL


class TestRuntimeModeSwitch:
    """Проверяет переключение потока при смене режима детектора в runtime."""

    def test_optical_to_thermal_switches_to_ik_url(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        mock_camera.switch_url.reset_mock()

        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pf.process_frame(frame)

        mock_camera.switch_url.assert_called_once_with(THERMAL_URL)

    def test_thermal_to_optical_switches_to_optical_url(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        mock_camera.switch_url.reset_mock()

        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pf.process_frame(frame)

        mock_camera.switch_url.assert_called_once_with(OPTICAL_URL)

    def test_no_switch_when_mode_unchanged(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        mock_camera.switch_url.reset_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for _ in range(10):
            pf.process_frame(frame)

        mock_camera.switch_url.assert_not_called()

    def test_multiple_switches_use_correct_urls(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        mock_camera.switch_url.reset_mock()

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL
        pf.process_frame(frame)

        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf.process_frame(frame)

        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL
        pf.process_frame(frame)

        assert mock_camera.switch_url.call_args_list == [
            call(THERMAL_URL),
            call(OPTICAL_URL),
            call(THERMAL_URL),
        ]


class TestTrackerResetOnSwitch:
    """Проверяет сброс трекера при смене потока."""

    def test_tracker_reset_on_mode_change(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        assert pf.tracker is not None
        pf.tracker = MagicMock(spec=CentroidTracker)

        mock_detector_manager.get_current_mode.return_value = DetectorMode.THERMAL
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pf.process_frame(frame)

        pf.tracker.reset.assert_called_once()

    def test_tracker_not_reset_when_mode_unchanged(
        self, cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
    ):
        mock_detector_manager.get_current_mode.return_value = DetectorMode.OPTICAL
        pf = _make_process_frame(
            cam_cfg, mock_camera, mock_detector_manager, mock_auto_ptz_manager
        )
        pf.tracker = MagicMock(spec=CentroidTracker)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pf.process_frame(frame)

        pf.tracker.reset.assert_not_called()


class TestDetectorSwitchIntegrity:
    """Проверяет, что после переключения используется новый детектор."""

    def test_new_detector_used_after_switch(
        self, cam_cfg, mock_camera, mock_auto_ptz_manager
    ):
        optical_detector = MagicMock(spec=ObjectDetector)
        optical_detector.detect.return_value = []
        thermal_detector = MagicMock(spec=ObjectDetector)
        thermal_detector.detect.return_value = []

        manager = MagicMock(spec=DetectorManager)
        manager.get_current_mode.return_value = DetectorMode.OPTICAL
        manager.get_detector.return_value = optical_detector

        pf = _make_process_frame(cam_cfg, mock_camera, manager, mock_auto_ptz_manager)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pf.process_frame(frame)
        optical_detector.detect.assert_called_once()
        thermal_detector.detect.assert_not_called()

        manager.get_current_mode.return_value = DetectorMode.THERMAL
        manager.get_detector.return_value = thermal_detector

        optical_detector.detect.reset_mock()
        pf.process_frame(frame)

        thermal_detector.detect.assert_called_once()
        optical_detector.detect.assert_not_called()


class TestCameraSwitchUrl:
    """Тестирует метод Camera.switch_url напрямую."""

    @patch("app.core.camera.manager.cv2.VideoCapture")
    def test_switch_url_changes_connection(self, mock_capture):
        from app.core.camera.manager import Camera
        from app.core.camera.models import CameraConnection

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_capture.return_value = mock_cap

        conn = CameraConnection(url=OPTICAL_URL)
        camera = Camera(conn)

        assert camera.current_url == OPTICAL_URL

        camera.switch_url(THERMAL_URL)

        assert camera.current_url == THERMAL_URL
        assert mock_capture.call_count == 2
        mock_capture.assert_called_with(THERMAL_URL)

    @patch("app.core.camera.manager.cv2.VideoCapture")
    def test_switch_url_noop_same_url(self, mock_capture):
        from app.core.camera.manager import Camera
        from app.core.camera.models import CameraConnection

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_capture.return_value = mock_cap

        conn = CameraConnection(url=OPTICAL_URL)
        camera = Camera(conn)

        initial_call_count = mock_capture.call_count
        camera.switch_url(OPTICAL_URL)

        assert mock_capture.call_count == initial_call_count

    @patch("app.core.camera.manager.cv2.VideoCapture")
    def test_switch_url_clears_last_frame(self, mock_capture):
        from app.core.camera.manager import Camera
        from app.core.camera.models import CameraConnection

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_capture.return_value = mock_cap

        conn = CameraConnection(url=OPTICAL_URL)
        camera = Camera(conn)
        camera._last_frame = np.ones((480, 640, 3), dtype=np.uint8)

        camera.switch_url(THERMAL_URL)

        assert camera.get_frame() is None


class TestFullPipelineStreamSwitch:
    """
    End-to-end тест: симулирует run_detection_sender с переключением режима.
    Гарантирует, что после switch кадры идут с нового потока.
    """

    def test_detection_sender_switches_stream_on_mode_change(
        self, cam_cfg, mock_auto_ptz_manager
    ):
        optical_frame = np.full((480, 640, 3), 100, dtype=np.uint8)
        thermal_frame = np.full((480, 640, 3), 200, dtype=np.uint8)

        optical_detector = MagicMock(spec=ObjectDetector)
        optical_detector.detect.return_value = []
        thermal_detector = MagicMock(spec=ObjectDetector)
        thermal_detector.detect.return_value = []

        manager = MagicMock(spec=DetectorManager)
        manager.get_current_mode.return_value = DetectorMode.OPTICAL
        manager.get_detector.return_value = optical_detector

        camera = MagicMock()
        camera.current_url = OPTICAL_URL
        camera.get_frame.return_value = optical_frame
        camera.switch_url = MagicMock()

        def switch_url_side_effect(url):
            if url == THERMAL_URL:
                camera.get_frame.return_value = thermal_frame
                camera.current_url = THERMAL_URL
            else:
                camera.get_frame.return_value = optical_frame
                camera.current_url = OPTICAL_URL

        camera.switch_url.side_effect = switch_url_side_effect

        pf = ProcessFrame(
            camera_id=1,
            auto_ptz_manager=mock_auto_ptz_manager,
            enable_auto_tracking=False,
            enable_detection=True,
            cam_cfg=cam_cfg,
            camera=camera,
            detector_manager=manager,
        )

        # --- Фаза 1: optical ---
        frame1 = camera.get_frame()
        pf.process_frame(frame1)

        passed_frame_1 = optical_detector.detect.call_args[0][0]
        assert np.array_equal(passed_frame_1, optical_frame), \
            "Фаза OPTICAL: детектор должен получить оптический кадр"

        # --- Переключаем на thermal ---
        manager.get_current_mode.return_value = DetectorMode.THERMAL
        manager.get_detector.return_value = thermal_detector

        frame2 = camera.get_frame()
        pf.process_frame(frame2)

        camera.switch_url.assert_called_with(THERMAL_URL)

        # Следующий кадр уже с теплового потока
        frame3 = camera.get_frame()
        pf.process_frame(frame3)

        passed_frame_3 = thermal_detector.detect.call_args[0][0]
        assert np.array_equal(passed_frame_3, thermal_frame), \
            "Фаза THERMAL: детектор должен получить тепловизионный кадр"

        # --- Переключаем обратно на optical ---
        manager.get_current_mode.return_value = DetectorMode.OPTICAL
        manager.get_detector.return_value = optical_detector
        optical_detector.detect.reset_mock()

        frame4 = camera.get_frame()
        pf.process_frame(frame4)

        camera.switch_url.assert_called_with(OPTICAL_URL)

        frame5 = camera.get_frame()
        pf.process_frame(frame5)

        passed_frame_5 = optical_detector.detect.call_args[0][0]
        assert np.array_equal(passed_frame_5, optical_frame), \
            "Обратно в OPTICAL: детектор должен получить оптический кадр"
