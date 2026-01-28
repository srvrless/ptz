from __future__ import annotations

import threading
import time
from typing import Dict, Optional

import cv2

from app.core.camera.models import CameraConnection
from logger.setup_logger import get_logger  # используем твой логгер

logger = get_logger("camera_manager")


class Camera:
    """
    Обёртка над cv2.VideoCapture с фоновым чтением последнего кадра.
    """

    def __init__(self, conn: CameraConnection):
        self._conn = conn
        self._cap = cv2.VideoCapture(conn.url)
        self._frame_lock = threading.Lock()
        self._last_frame = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        if not self._cap.isOpened():
            logger.error(f"Не удалось открыть RTSP-поток: {conn.url}")
        else:
            logger.info(f"Открыто подключение к камере: {conn.url}")

        self.start()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self) -> None:
        """
        Бесконечно читает кадры из VideoCapture и сохраняет последний успешный.
        При ошибках пытается реконнектиться с экспоненциальным бэк-оффом.
        """
        reconnect_attempts = 0
        while self._running:
            if not self._cap.isOpened():
                logger.warning(
                    f"Поток камеры {self._conn.url} закрыт, попытка реконнекта ({reconnect_attempts + 1})"
                )
                # Экспоненциальный бэк-офф: 0.5s, 1s, 2s, 4s, 8s
                delay = min(0.5 * (2**reconnect_attempts), 8.0)
                time.sleep(delay)
                self._cap.release()
                self._cap = cv2.VideoCapture(self._conn.url)
                reconnect_attempts += 1
                if reconnect_attempts > 5:
                    logger.error(
                        f"Не удалось переподключиться к камере {self._conn.url}"
                    )
                    break
                continue

            ok, frame = self._cap.read()
            if not ok:
                logger.warning(f"Ошибка чтения кадра с камеры {self._conn.url}")
                continue

            reconnect_attempts = 0
            with self._frame_lock:
                self._last_frame = frame

        logger.info(f"Reader loop завершён для камеры {self._conn.url}")

    def get_frame(self):
        """
        Возвращает последний полученный кадр (или None, если ещё не было).
        """
        with self._frame_lock:
            return self._last_frame.copy() if self._last_frame is not None else None

    def stop(self) -> None:
        """
        Останавливает чтение и освобождает ресурсы.
        """
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._cap.isOpened():
            self._cap.release()
        logger.info(f"Камера остановлена: {self._conn.url}")


class CameraManager:
    """
    Хранит и переиспользует подключения к камерам по camera_id.
    Отвечает только за низкоуровневый доступ к кадрам.
    """

    def __init__(self):
        self._cameras: Dict[str, Camera] = {}
        self._lock = threading.Lock()

    def get_or_create(self, camera_id: int, conn: CameraConnection) -> Camera:
        """
        Получить объект камеры по ID. Если ещё не создан — создать.
        """
        with self._lock:
            cam = self._cameras.get(camera_id)
            if cam is None:
                logger.info(f"Создание нового подключения для камеры {camera_id}")
                cam = Camera(conn)
                self._cameras[camera_id] = cam
            return cam

    def get(self, camera_id: int) -> Optional[Camera]:
        with self._lock:
            return self._cameras.get(camera_id)

    def release(self, camera_id: int) -> None:
        """
        Остановить и удалить конкретную камеру.
        """
        with self._lock:
            cam = self._cameras.pop(camera_id, None)
        if cam:
            cam.stop()

    def stop_all(self) -> None:
        """
        Остановить все камеры.
        """
        with self._lock:
            cams = list(self._cameras.values())
            self._cameras.clear()
        for cam in cams:
            cam.stop()
        logger.info("Все камеры остановлены")


camera_manager = CameraManager()
