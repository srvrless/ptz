from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock, Thread, Timer
from typing import Dict, Optional
from contextlib import contextmanager

from fastapi import HTTPException

from app.config.settings import AppConfig, CameraConfig, DetectorMode
from app.core.camera.manager import CameraConnection, CameraManager
from app.core.detection.yolo_detector import DetectorManager
from app.core.streaming.mjpeg import run_detection_sender, _default_connection_factory
from app.core.ptz.manager import PTZCameraManager
from app.core.tracking.auto_ptz_manager import AutoPTZManager
from app.exceptions import CameraNotFoundError
from app.services.camera_gateway_client import CameraGatewayClient
from logger.setup_logger import get_logger

logger = get_logger("camera_service")


@dataclass
class _ClientSession:
    camera_id: int
    worker_thread: Thread
    stop_event: Event
    ttl_timer: Optional[Timer] = None
    ttl_seq: int = 0


class CameraService:
    def __init__(
        self,
        camera_manager: CameraManager,
        ptz_manager: PTZCameraManager,
        auto_ptz_manager: AutoPTZManager,
        detector_manager: DetectorManager,
        config: AppConfig,
        camera_gateway: CameraGatewayClient,
        camera_ttl_seconds: float = 600
    ) -> None:
        self.camera_manager = camera_manager
        self.ptz_manager = ptz_manager
        self.auto_ptz_manager = auto_ptz_manager
        self.detector_manager = detector_manager
        self.config = config
        self._lock = Lock()
        self._sessions: Dict[str, _ClientSession] = {}
        self._camera_gateway = camera_gateway
        self.camera_ttl_seconds = camera_ttl_seconds
        self._ttl_seq = 0

    def get_camera_config(
        self,
        camera_id: int,
    ) -> CameraConfig:
        """Получить конфиг камеры из БД. Конвертация внутри with — объект не detached."""
        camera_cfg = self._camera_gateway.get_camera_config_by_id(camera_id)
        if camera_cfg is None:
            logger.warning(f"Camera not found: {camera_id}")
            raise CameraNotFoundError(str(camera_id))
        return camera_cfg

    def _rtsp_url_for_current_mode(self, cam_cfg) -> str:
        """Возвращает RTSP URL, соответствующий текущему режиму детектора."""
        current_mode = self.detector_manager.get_current_mode()
        if current_mode == DetectorMode.THERMAL:
            return cam_cfg.rtsp_url_ik
        return cam_cfg.rtsp_url

    @contextmanager
    def _claim_camera_or_rollback(
        self,
        camera_id: int,
        client_id: str,
    ) -> CameraConfig:
        """
        Захватывает камеру в gateway и гарантирует release при любой ошибке
        в вызывающем коде.
        """
        try:
            cam_cfg = self._camera_gateway.claim_camera(camera_id, client_id)
        except HTTPException:
            # gateway уже вернул корректный HTTP-статус (например, 423)
            raise
        except Exception as exc:
            # httpx может кидать HTTPStatusError на 4xx — нормализуем 423
            if getattr(exc, "response", None) is not None:
                status = getattr(exc.response, "status_code", None)
                if status == 423:
                    raise HTTPException(status_code=423, detail="Камера занята")
                if status == 404:
                    raise HTTPException(status_code=404, detail="Камера не найдена")
            raise

        try:
            yield cam_cfg
        except Exception:
            # Любая ошибка после успешного claim — откатываем занятость.
            try:
                self._camera_gateway.release_camera(camera_id, client_id)
            except Exception:
                logger.exception(
                    "Failed to rollback camera lock in gateway after error: "
                    "camera=%s client=%s",
                    camera_id,
                    client_id,
                )
            raise

    @contextmanager
    def _ptz_ownership(self, camera_id: int, client_id: str, cam_cfg):
        """Гарантирует установку и очистку владельца PTZ."""
        self.ptz_manager.set_owner(camera_id, client_id)
        try:
            if not self.ptz_manager.is_initialized(camera_id):
                self._ensure_camera_available(camera_id, cam_cfg)
            yield
        except Exception:
            self.ptz_manager.clear_owner(camera_id, client_id)
            raise

    def _ensure_streaming_available(self, camera_id: int) -> None:
        """
        Синхронно проверяет доступность сокет‑сервиса для стриминга.
        Бросает 5xx, если соединение установить не удалось.
        """
        try:
            sock = _default_connection_factory()
            sock.close()

        except Exception as exc:
            logger.error(
                "Failed to connect to streaming socket for camera=%s: %s",
                camera_id,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="Не удалось подключиться к сервису стриминга",
            ) from exc


    def _ensure_camera_available(self, camera_id: int, cam_cfg) -> None:
        """
        Синхронно проверяет доступность PTZ‑контроллера (ONVIF / TMS‑20).
        Бросает 5xx, если соединение установить не удалось.
        """
        try:
            self.ptz_manager.init_camera(camera_id, cam_cfg)

        except Exception as exc:
            logger.error(
                "Failed connect to PTZ controller for camera=%s: %s",
                camera_id,
                exc,
            )
            raise HTTPException(
                status_code=502,
                detail="Не удалось подключиться к камере",
            ) from exc

    def _get_camera_for_current_mode(self, camera_id: int, cam_cfg):
        """Создаёт/получает камеру и гарантирует, что она на правильном потоке."""
        url = self._rtsp_url_for_current_mode(cam_cfg)
        conn = CameraConnection(url=url)
        camera = self.camera_manager.get_or_create(camera_id, conn)
        camera.switch_url(url)
        return camera

    def _schedule_ttl_locked(self, client_id: str, camera_id: int) -> None:
        """
        Планирует авто-release камеры через `self.camera_ttl_seconds`.

        Требование: вызывающий код должен удерживать `self._lock`.
        """
        sess = self._sessions[client_id]

        # Инвалидируем предыдущий таймер/запуск.
        if sess.ttl_timer is not None:
            try:
                sess.ttl_timer.cancel()
            except Exception:
                logger.exception(
                    "Failed to cancel ttl timer: camera=%s client=%s",
                    camera_id,
                    client_id,
                )
            sess.ttl_timer = None

        self._ttl_seq += 1
        sess.ttl_seq = self._ttl_seq
        expected_seq = sess.ttl_seq

        timer = Timer(
            self.camera_ttl_seconds,
            self._ttl_timeout,
            args=(client_id, camera_id, expected_seq),
        )
        timer.daemon = True
        sess.ttl_timer = timer
        timer.start()

    def _invalidate_ttl_locked(self, client_id: str) -> None:
        """Отменяет текущий таймер и увеличивает seq для защиты от гонок."""
        sess = self._sessions.get(client_id)
        if sess is None:
            return

        if sess.ttl_timer is not None:
            try:
                sess.ttl_timer.cancel()
            except Exception:
                logger.exception(
                    "Failed to cancel ttl timer: camera=%s client=%s",
                    sess.camera_id,
                    client_id,
                )
            sess.ttl_timer = None

        self._ttl_seq += 1
        sess.ttl_seq = self._ttl_seq

    def _ttl_timeout(
        self, client_id: str, expected_camera_id: int, expected_seq: int
    ) -> None:
        """
        Коллбек таймера TTL (runs в отдельном потоке).

        Идемпотентный: если за время TTL сменился camera_id или произошёл reset,
        то просто ничего не делаем.
        """
        with self._lock:
            sess = self._sessions.get(client_id)
            if sess is None:
                return
            if sess.camera_id != expected_camera_id:
                return
            if sess.ttl_seq != expected_seq:
                return

        try:
            self.stop_selected_camera(client_id)
        except Exception:
            logger.exception(
                "TTL auto-release failed: camera=%s client=%s",
                expected_camera_id,
                client_id,
            )

    def select_camera(
        self,
        camera_id: int,
        client_id: str,
        enable_detection: bool = True,
        enable_auto_tracking: bool = True,
    ) -> None:
        # 1) Захватываем камеру в gateway с автоматическим rollback при ошибке.
        with self._claim_camera_or_rollback(camera_id, client_id) as cam_cfg:
            with self._ptz_ownership(camera_id, client_id, cam_cfg):
                self._ensure_streaming_available(camera_id)
                auto_ptz = self.auto_ptz_manager.get_or_create(
                    camera_id, client_id, cam_cfg
                )
    
                with self._lock:
                    existing = self._sessions.get(client_id)

                    # Проверка дубликата сессии
                    if (
                        existing
                        and existing.camera_id == camera_id
                        and existing.worker_thread.is_alive()
                    ):
                        # Камера та же и воркер жив — продлеваем TTL.
                        self._schedule_ttl_locked(client_id, camera_id)
                        return

                    old_camera_id: Optional[int] = (
                        existing.camera_id if existing is not None else None
                    )

                    # 2) Останавливаем старый detection-воркер и освобождаем старую камеру.
                    self._stop_worker_locked(client_id)

                    if old_camera_id is not None and old_camera_id != camera_id:
                        self.camera_manager.release(old_camera_id)
                        # Освобождаем lock в gateway за старую камеру (best-effort).
                        try:
                            self._camera_gateway.release_camera(
                                old_camera_id, client_id
                            )
                        except Exception:
                            logger.exception(
                                "Failed to release camera lock in gateway: "
                                "camera=%s client=%s",
                                old_camera_id,
                                client_id,
                            )

                    # 3) Готовим камеру и проверяем доступность сокет‑сервиса.
                    camera = self._get_camera_for_current_mode(camera_id, cam_cfg)

                    # 4) Запускаем detection-воркер и сохраняем сессию.
                    stop_event = Event()
                    worker = Thread(
                        target=run_detection_sender,
                        kwargs=dict(
                            camera=camera,
                            camera_id=camera_id,
                            auto_ptz=auto_ptz,
                            cam_cfg=cam_cfg,
                            detector_manager=self.detector_manager,
                            enable_detection=enable_detection,
                            enable_auto_tracking=enable_auto_tracking,
                            stop_event=stop_event,
                        ),
                        daemon=True,
                    )
                    worker.start()

                    self._sessions[client_id] = _ClientSession(
                        camera_id=camera_id, worker_thread=worker, stop_event=stop_event
                    )
                    self._schedule_ttl_locked(client_id, camera_id)

                    logger.info(
                        "Selected camera=%s for client=%s", camera_id, client_id
                    )

    def get_selected_camera_id(self, client_id: str) -> Optional[int]:
        with self._lock:
            sess = self._sessions.get(client_id)
            return None if sess is None else sess.camera_id

    def stop_selected_camera(self, client_id: str) -> None:
        with self._lock:
            sess = self._sessions.get(client_id)
            old_camera_id = None if sess is None else sess.camera_id
            self._stop_worker_locked(client_id)
            if old_camera_id is not None:
                self.camera_manager.release(old_camera_id)
                # Снимаем локальный ownership (если не владелец — 423).
                self.ptz_manager.clear_owner(old_camera_id, client_id)
                # Освобождаем lock в gateway (best-effort)
                try:
                    self._camera_gateway.release_camera(old_camera_id, client_id)
                except Exception:
                    logger.exception(
                        "Failed to release camera lock in gateway: camera=%s client=%s",
                        old_camera_id,
                        client_id,
                    )

            if client_id in self._sessions:
                del self._sessions[client_id]

    def touch_selected_camera(self, *, camera_id: int, client_id: str) -> None:
        """
        Обновить TTL для уже выбранной камеры.

        Используется PTZ-ручками как "keep-alive":
        таймер переустанавливается на максимум `camera_ttl_seconds` (10 минут).
        """
        with self._lock:
            sess = self._sessions.get(client_id)
            if sess is None or sess.camera_id != camera_id:
                return
            # Поскольку TTL фиксирован (10 минут по определению), "не больше 10"
            # гарантируется самим таймером: мы каждый раз ставим полную длительность.
            self._schedule_ttl_locked(client_id, camera_id)

    def _stop_worker_locked(self, client_id: str) -> None:
        sess = self._sessions.get(client_id)
        if sess is None:
            return

        # Останавливаем TTL-таймер и инвалидация seq для защиты от гонок.
        self._invalidate_ttl_locked(client_id)

        sess.stop_event.set()

        if sess.worker_thread.is_alive():
            sess.worker_thread.join(timeout=5)
            if sess.worker_thread.is_alive():
                logger.error(
                    "Detection worker for camera %s (client=%s) did not stop within 5s — possible data leak to socket",
                    sess.camera_id,
                    client_id,
                )

    def stop_all_sessions(self) -> None:
        """Graceful cleanup активных сессий (в т.ч. отмена TTL-таймеров)."""
        with self._lock:
            client_ids = list(self._sessions.keys())

        for client_id in client_ids:
            try:
                self.stop_selected_camera(client_id)
            except Exception:
                logger.exception(
                    "Failed to stop camera session on shutdown: client=%s",
                    client_id,
                )
