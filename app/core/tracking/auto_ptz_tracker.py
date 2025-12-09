from __future__ import annotations

import math
from typing import List, Optional, Tuple, Any

from logger.setup_logger import get_logger

from app.core.ptz.base import BasePTZController
from app.core.ptz.manager import ptz_camera_manager

logger = get_logger("auto_ptz_tracker")


class AutoPTZTracker:
    """
    Автоматическое слежение PTZ-камеры за ОДНИМ объектом.

    Предполагается, что каждый объект в `objects` имеет минимум поля:
      - bbox: (x1, y1, x2, y2) в пикселях кадра
      - conf: float, уверенность детекции
      - track_id: int | None, устойчивый ID трека

    Если у тебя другие имена полей – поправь обращения к ним в этом классе.
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

        self._current_target_id: Optional[int] = None
        self._lost_frames: int = 0

    # --- вспомогательные методы работы с боксами ---

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
        """
        Относительная диагональ бокса: 0..1.
        Используем как грубую оценку “насколько объект крупный / зум сильный”.
        """
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
        """
        Чем крупнее объект (сильнее зум) – тем меньше возвращаемое значение.
        Это снижает усиление при большом приближении, чтобы не было рысканья.
        """
        rel = self._bbox_diag_ratio(bbox, frame_shape)
        #  rel = 0.0  → scale ≈ 1.0
        #  rel = 0.3  → scale ≈ 0.53
        #  rel = 0.5  → scale ≈ 0.40
        return 1.0 / (1.0 + 3.0 * rel)

    def _error_to_speed(self, err: float, k: float) -> float:
        """
        Преобразует нормированную ошибку в скорость [-1..1].

        - внутри dead_zone → 0
        - снаружи → модуль не меньше min_speed
        """
        if abs(err) < self.dead_zone:
            return 0.0

        v = k * err

        # если скорость получилась слишком маленькой – поджимаем до min_speed
        if abs(v) < self.min_speed:
            v = math.copysign(self.min_speed, v)

        # финальный кламп в допустимый диапазон
        if v > 1.0:
            v = 1.0
        elif v < -1.0:
            v = -1.0

        return v

    # --- выбор и удержание цели ---

    def _choose_target(self, objects: List[Any]) -> Optional[Any]:
        """
        Возвращает выбранный объект или None.
        """
        if not objects:
            # никого в кадре – увеличиваем счётчик потерь
            if self._current_target_id is not None:
                self._lost_frames += 1
                if self._lost_frames > self.max_lost_frames:
                    logger.info("AutoPTZ: цель потеряна, сбрасываем track_id")
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
                "AutoPTZ: не видим цель id=%s %d кадров, выбираем новую",
                self._current_target_id,
                self._lost_frames,
            )
            self._current_target_id = None
            self._lost_frames = 0

        # выбираем новую цель:
        # сначала по уверенности, при равенстве – по площади бокса
        def _score(o: Any) -> Tuple[float, int]:
            bbox = getattr(o, "bbox")
            conf = float(getattr(o, "conf", 0.0))
            return conf, self._bbox_area(bbox)

        best = max(objects, key=_score)
        self._current_target_id = getattr(best, "track_id", None)
        logger.info(
            "AutoPTZ: выбрана новая цель track_id=%s, conf=%.2f, bbox=%s",
            self._current_target_id,
            float(getattr(best, "conf", 0.0)),
            getattr(best, "bbox"),
        )
        return best

    # --- основной публичный метод ---

    def update(self, frame_shape: Tuple[int, int, int], objects: List[Any]) -> None:
        """
        Основной метод, который нужно вызывать каждый кадр.

        frame_shape: shape кадра (h, w, c)
        objects: список детекций/треков (см. описание класса).
        """
        if self._controller is None:
            return

        target = self._choose_target(objects)
        if target is None:
            # цели нет – останавливаем пан/тилт, но не трогаем зум
            try:
                self._controller.stop(pan_tilt=True, zoom=False)
            except Exception:
                logger.exception("AutoPTZ: ошибка при остановке PTZ")
            return

        h, w = frame_shape[:2]
        bbox = getattr(target, "bbox")
        cx, cy = self._bbox_center(bbox)

        # центр кадра
        cx_frame = w / 2.0
        cy_frame = h / 2.0

        # нормированные ошибки: >0 → объект справа/выше центра
        err_x = (cx - cx_frame) / cx_frame
        err_y = (cy_frame - cy) / cy_frame  # ось Y перевёрнута

        # масштаб в зависимости от размера бокса (аналог "учёта зума")
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
