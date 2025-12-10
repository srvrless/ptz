from __future__ import annotations

import math
from typing import List, Optional, Tuple, Any

from logger.setup_logger import get_logger

from app.core.ptz.base import BasePTZController
from app.core.ptz.manager import ptz_camera_manager

logger = get_logger("auto_ptz_tracker")


class AutoPTZTracker:
    """
    Слежение PTZ-камеры за ОДНИМ объектом (по track_id).
    """

    def __init__(
        self,
        camera_id: str,
        *,
        kp_pan: float = 0.6,
        kp_tilt: float = 0.6,
        dead_zone: float = 0.003,
        max_lost_frames: int = 15,
        min_speed: float = 0.01,
    ) -> None:
        self.camera_id = camera_id
        self.kp_pan = kp_pan
        self.kp_tilt = kp_tilt
        self.dead_zone = dead_zone
        self.max_lost_frames = max_lost_frames
        self.min_speed = min_speed

        self._controller: Optional[BasePTZController] = ptz_camera_manager.get_controller(
            camera_id
        )
        if self._controller is None:
            logger.warning("AutoPTZ: контроллер для камеры %s не найден", camera_id)

        # track_id текущей цели, задаётся ИЗВНЕ
        self._current_target_id: Optional[int] = None
        self._lost_frames: int = 0

    # --- публичный API управления ---
    def set_target(self, track_id: Optional[int]) -> None:
        """
        Выбрать конкретный track_id для слежения.
        None = выкл. автослежение.
        """
        self._current_target_id = track_id
        self._lost_frames = 0
        logger.info(
            "AutoPTZ: set_target camera=%s track_id=%s",
            self.camera_id,
            track_id,
        )

    def clear_target(self) -> None:
        """
        Полностью выключить слежение за объектом и остановить PTZ.
        """
        self._current_target_id = None
        self._lost_frames = 0
        try:
            if self._controller is not None:
                # останавливаем только пан/тилт, зум не трогаем
                self._controller.stop(pan_tilt=True, zoom=False)
        except Exception:
            logger.exception("AutoPTZ: ошибка при stop() в clear_target")
        logger.info("AutoPTZ: clear_target camera=%s", self.camera_id)

    def get_target(self) -> Optional[int]:
        """Текущий выбранный track_id (или None, если никого не трекаем)."""
        return self._current_target_id

    def follow(self, track_id: int) -> None:
        """
        Включить слежение за объектом с заданным track_id.
        """
        self._current_target_id = track_id
        self._lost_frames = 0
        logger.info(
            "AutoPTZ: включено слежение за track_id=%s на камере %s",
            track_id,
            self.camera_id,
        )

    def stop_follow(self) -> None:
        """
        Полностью выключить авто-слежение.
        """
        self._current_target_id = None
        self._lost_frames = 0
        try:
            if self._controller is not None:
                # останавливаем пан/тилт, зум не трогаем
                self._controller.stop(pan_tilt=True, zoom=False)
        except Exception:
            logger.exception("AutoPTZ: ошибка stop() при выключении слежения")

        logger.info("AutoPTZ: слежение выключено на камере %s", self.camera_id)

    def get_current_target_id(self) -> Optional[int]:
        """
        Удобно для дебага/эндпоинта статуса.
        """
        return self._current_target_id

    # --- вспомогательные методы работы с боксами (как было) ---
    @staticmethod
    def _bbox_center(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    @staticmethod
    def _bbox_area(bbox: Tuple[int, int, int, int]) -> int:
        x1, y1, x2, y2 = bbox
        return max(0, x2 - x1) * max(0, y2 - y1)

    @staticmethod
    def _bbox_diag_ratio(
        bbox: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int, int],
    ) -> float:
        x1, y1, x2, y2 = bbox
        w_box = max(1, x2 - x1)
        h_box = max(1, y2 - y1)
        diag_box = math.hypot(w_box, h_box)

        h, w = frame_shape[:2]
        diag_frame = math.hypot(w, h)

        return diag_box / diag_frame

    def _zoom_scale(
        self,
        bbox: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int, int],
    ) -> float:
        rel = self._bbox_diag_ratio(bbox, frame_shape)
        return 1.0 / (1.0 + 3.0 * rel)

    def _error_to_speed(self, err: float, k: float) -> float:
        if abs(err) < self.dead_zone:
            return 0.0

        v = k * err

        if abs(v) < self.min_speed:
            v = math.copysign(self.min_speed, v)

        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0

        return v

    # --- выбор и удержание цели (НОВЫЙ, без авто-выбора) ---

    def _choose_target(self, objects: List[Any]) -> Optional[Any]:
        """
        Возвращает объект с _current_target_id или None,
        если слежение выключено / цель потеряна.
        """
        if not objects:
            # никого в кадре – увеличиваем счётчик потерь
            if self._current_target_id is not None:
                self._lost_frames += 1
                if self._lost_frames > self.max_lost_frames:
                    logger.info(
                        "AutoPTZ: цель id=%s потеряна (%d кадров), сбрасываем track_id",
                        self._current_target_id,
                        self._lost_frames,
                    )
                    self._current_target_id = None
                    self._lost_frames = 0
            return None

        # если есть текущая цель – пытаемся её найти в новых детекциях
        if self._current_target_id is not None:
            for obj in objects:
                if getattr(obj, "track_id", None) == self._current_target_id:
                    # нашли – продолжаем трек
                    self._lost_frames = 0
                    return obj

            # в этом кадре объекта с таким track_id нет
            self._lost_frames += 1
            if self._lost_frames <= self.max_lost_frames:
                # ждём ещё немного, не перескакиваем на другой объект
                return None

            # окончательно потеряли
            logger.info(
                "AutoPTZ: не видим цель id=%s %d кадров, сбрасываем track_id",
                self._current_target_id,
                self._lost_frames,
            )
            self._current_target_id = None
            self._lost_frames = 0

        # если сюда дошли и current_target_id == None — НИКОГО автоматически не выбираем
        # ждём явный set_target(...) из API
        return None

    # --- основной публичный метод (как было, но с новым _choose_target) ---

    def update(self, frame_shape: Tuple[int, int, int], objects: List[Any]) -> None:
        """
        Основной метод, который нужно вызывать каждый кадр.

        frame_shape: shape кадра (h, w, c)
        objects: список детекций/треков (см. описание класса).
        """
        if self._controller is None:
            return

        target = self._choose_target(objects)

        # если автослежение выключено (цель не выбрана) – вообще не шевелим PTZ
        if self._current_target_id is None:
            return

        if target is None:
            # цель выбрана, но в этом кадре мы её не видим – тормозим камеру
            try:
                self._controller.stop(pan_tilt=True, zoom=False)
            except Exception:
                logger.exception("AutoPTZ: ошибка при остановке PTZ")
            return

        # дальше оставляем твою логику вычисления vx/vy и continuous_move(...)
        h, w = frame_shape[:2]
        bbox = getattr(target, "bbox")
        cx, cy = self._bbox_center(bbox)

        cx_frame = w / 2.0
        cy_frame = h / 2.0

        err_x = (cx - cx_frame) / cx_frame
        err_y = (cy_frame - cy) / cy_frame  # ось Y перевёрнута

        scale = self._zoom_scale(bbox, frame_shape)

        vx = self._error_to_speed(err_x, self.kp_pan * scale)
        vy = self._error_to_speed(err_y, self.kp_tilt * scale)

        try:
            if vx == 0.0 and vy == 0.0:
                self._controller.stop(pan_tilt=True, zoom=False)
            else:
                self._controller.continuous_move(vx, vy, zoom=0.0)
        except Exception:
            logger.exception("AutoPTZ: ошибка continuous_move/stop")
