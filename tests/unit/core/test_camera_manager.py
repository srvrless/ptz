from unittest.mock import MagicMock, patch

from app.core.camera.manager import Camera, CameraManager
from app.core.camera.models import CameraConnection


class TestCamera:
    """Тесты для Camera."""

    @patch("app.core.camera.manager.cv2.VideoCapture")
    def test_camera_initialization(self, mock_capture):
        """Проверяет инициализацию камеры."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        conn = CameraConnection(url="rtsp://example.com/stream")
        camera = Camera(conn)

        assert camera._conn == conn
        assert camera._running is True

    @patch("app.core.camera.manager.cv2.VideoCapture")
    def test_camera_stop(self, mock_capture):
        """Проверяет остановку камеры."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_capture.return_value = mock_cap_instance

        conn = CameraConnection(url="rtsp://example.com/stream")
        camera = Camera(conn)
        camera.stop()

        assert camera._running is False
        mock_cap_instance.release.assert_called()


class TestCameraManager:
    """Тесты для CameraManager."""

    @patch("app.core.camera.manager.Camera")
    def test_get_or_create_new_camera(self, mock_camera_class):
        """Проверяет создание новой камеры."""
        mock_camera_instance = MagicMock()
        mock_camera_class.return_value = mock_camera_instance

        manager = CameraManager()
        conn = CameraConnection(url="rtsp://example.com/stream")

        camera = manager.get_or_create("camera1", conn)

        assert camera == mock_camera_instance
        assert "camera1" in manager._cameras

    @patch("app.core.camera.manager.Camera")
    def test_get_or_create_reuses_existing(self, mock_camera_class):
        """Проверяет переиспользование существующей камеры."""
        mock_camera_instance = MagicMock()
        mock_camera_class.return_value = mock_camera_instance

        manager = CameraManager()
        conn = CameraConnection(url="rtsp://example.com/stream")

        camera1 = manager.get_or_create("camera1", conn)
        camera2 = manager.get_or_create("camera1", conn)

        assert camera1 == camera2
        mock_camera_class.assert_called_once()

    @patch("app.core.camera.manager.Camera")
    def test_release_camera(self, mock_camera_class):
        """Проверяет удаление камеры."""
        mock_camera_instance = MagicMock()
        mock_camera_class.return_value = mock_camera_instance

        manager = CameraManager()
        conn = CameraConnection(url="rtsp://example.com/stream")
        manager.get_or_create("camera1", conn)

        manager.release("camera1")

        mock_camera_instance.stop.assert_called()
        assert "camera1" not in manager._cameras

    @patch("app.core.camera.manager.Camera")
    def test_stop_all_cameras(self, mock_camera_class):
        """Проверяет остановку всех камер."""
        mock_camera_instance1 = MagicMock()
        mock_camera_instance2 = MagicMock()
        mock_camera_class.side_effect = [mock_camera_instance1, mock_camera_instance2]

        manager = CameraManager()
        conn = CameraConnection(url="rtsp://example.com/stream")

        manager.get_or_create("camera1", conn)
        manager.get_or_create("camera2", conn)

        manager.stop_all()

        mock_camera_instance1.stop.assert_called()
        mock_camera_instance2.stop.assert_called()
        assert len(manager._cameras) == 0
