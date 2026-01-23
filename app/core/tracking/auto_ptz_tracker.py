from __future__ import annotations

import math
import time
from typing import Any, List, Optional, Tuple

from app.core.ptz.base import BasePTZController
from app.core.ptz.manager import ptz_camera_manager
from logger.setup_logger import get_logger

logger = get_logger("auto_ptz_tracker")


class AutoPTZTracker:
    """
    Слежение PTZ-камеры за ОДНИМ объектом (по track_id).

    Улучшения (без изменения внешнего API):
    - PD-регулятор + lookahead (компенсация задержки)
    - защита от "торможения" при большом bbox (scale clamp + override)
    - поведение при кратковременной потере: не стопаем сразу, держим/затухаем команду
    - сглаживание команд (EMA)
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

        self._controller: Optional[BasePTZController] = (
            ptz_camera_manager.get_controller(camera_id)
        )
        if self._controller is None:
            logger.warning("AutoPTZ: контроллер для камеры %s не найден", camera_id)

        # track_id текущей цели, задаётся ИЗВНЕ
        self._current_target_id: Optional[int] = None
        self._lost_frames: int = 0

        # ====== NEW: внутреннее состояние регулятора (не меняет API) ======
        self._prev_t: Optional[float] = None
        self._prev_err_x: float = 0.0
        self._prev_err_y: float = 0.0

        # последние отправленные команды (для удержания/затухания при потере)
        self._cmd_vx: float = 0.0
        self._cmd_vy: float = 0.0

        # коэффициенты D (без параметров наружу — безопасно для текущего кода)
        self._kd_pan: float = 0.25 * self.kp_pan
        self._kd_tilt: float = 0.25 * self.kp_tilt

        # оценка задержки пайплайна (кадр->детект->команда->движение)
        self._lead_time: float = 0.12  # 120мс — типичный старт, можно подстроить

        # сглаживание команд (0..1): больше => плавнее, меньше => быстрее реагирует
        self._cmd_smooth: float = 0.35

        # потеря цели: сколько кадров НЕ стопать сразу (часто YOLO моргает 1-2 кадра)
        self._lost_grace_frames: int = 2

        # затухание команды, если цель потеряна дольше grace
        self._lost_decay: float = 0.85

        # минимальный scale, чтобы “близкая быстрая цель” не душилась
        self._scale_min: float = 0.35
        # если ошибка большая — игнорируем scale и даём максимум реакции
        self._scale_override_err: float = 0.22

        # ограничение на производную ошибки (чтоб не улетало)
        self._derr_limit: float = 6.0  # (норм. ошибка)/сек

    # --- публичный API управления ---
    def set_target(self, track_id: Optional[int]) -> None:
        self._current_target_id = track_id
        self._lost_frames = 0

        # reset регулятора
        self._prev_t = None
        self._prev_err_x = 0.0
        self._prev_err_y = 0.0
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0

        logger.info(
            "AutoPTZ: set_target camera=%s track_id=%s",
            self.camera_id,
            track_id,
        )

    def clear_target(self) -> None:
        self._current_target_id = None
        self._lost_frames = 0

        # reset регулятора
        self._prev_t = None
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0

        try:
            if self._controller is not None:
                self._controller.stop(pan_tilt=True, zoom=False)
        except Exception as exc:
            logger.exception(f"AutoPTZ: ошибка при stop() в clear_target {exc}")
        logger.info("AutoPTZ: clear_target camera=%s", self.camera_id)

    def get_target(self) -> Optional[int]:
        return self._current_target_id

    def follow(self, track_id: int) -> None:
        self._current_target_id = track_id
        self._lost_frames = 0

        # reset регулятора
        self._prev_t = None
        self._prev_err_x = 0.0
        self._prev_err_y = 0.0
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0

        logger.info(
            "AutoPTZ: включено слежение за track_id=%s на камере %s",
            track_id,
            self.camera_id,
        )

    def stop_follow(self) -> None:
        self._current_target_id = None
        self._lost_frames = 0

        # reset регулятора
        self._prev_t = None
        self._cmd_vx = 0.0
        self._cmd_vy = 0.0

        try:
            if self._controller is not None:
                self._controller.stop(pan_tilt=True, zoom=False)
        except Exception as exc:
            logger.exception(f"AutoPTZ: ошибка stop() при выключении слежения:  {exc}")

        logger.info("AutoPTZ: слежение выключено на камере %s", self.camera_id)

    def get_current_target_id(self) -> Optional[int]:
        return self._current_target_id

    # --- вспомогательные методы работы с боксами ---
    @staticmethod
    def _bbox_center(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

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
        # чуть менее агрессивная "душилка", чем было (3.0 -> 2.0)
        rel = self._bbox_diag_ratio(bbox, frame_shape)
        return 1.0 / (1.0 + 2.0 * rel)

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return lo if v < lo else hi if v > hi else v

    def _error_to_speed(self, v: float) -> float:
        # общий clamp + min_speed, dead_zone применяется выше на err_pred
        if abs(v) < self.min_speed and abs(v) > 0.0:
            v = math.copysign(self.min_speed, v)
        return self._clamp(v, -1.0, 1.0)

    # --- выбор и удержание цели (как было) ---
    def _choose_target(self, objects: List[Any]) -> Optional[Any]:
        if not objects:
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

        if self._current_target_id is not None:
            for obj in objects:
                if getattr(obj, "track_id", None) == self._current_target_id:
                    self._lost_frames = 0
                    return obj

            self._lost_frames += 1
            if self._lost_frames <= self.max_lost_frames:
                return None

            logger.info(
                "AutoPTZ: не видим цель id=%s %d кадров, сбрасываем track_id",
                self._current_target_id,
                self._lost_frames,
            )
            self._current_target_id = None
            self._lost_frames = 0

        return None

    # --- основной публичный метод (с улучшенной логикой управления) ---
    def update(self, frame_shape: Tuple[int, int, int], objects: List[Any]) -> None:
        if self._controller is None:
            return

        target = self._choose_target(objects)

        # если цель не выбрана – вообще не шевелим PTZ
        if self._current_target_id is None:
            return

        # dt для производной (и для lookahead)
        now = time.monotonic()
        if self._prev_t is None:
            dt = 1.0 / 25.0  # разумный дефолт
        else:
            dt = max(1e-3, now - self._prev_t)
        self._prev_t = now

        # ====== ЦЕЛЬ НЕ ВИДИМ В ЭТОМ КАДРЕ ======
        if target is None:
            # ВАЖНО: не стопаем сразу — иначе при моргании детектора камера тормозит и отстаёт
            if self._lost_frames <= self._lost_grace_frames:
                # держим последнюю команду
                vx = self._cmd_vx
                vy = self._cmd_vy
            else:
                # плавно затухаем
                self._cmd_vx *= self._lost_decay
                self._cmd_vy *= self._lost_decay
                vx = self._cmd_vx
                vy = self._cmd_vy

            try:
                if abs(vx) < self.min_speed and abs(vy) < self.min_speed:
                    self._controller.stop(pan_tilt=True, zoom=False)
                else:
                    self._controller.continuous_move(vx, vy, zoom=0.0)
            except Exception as exc:
                logger.exception(
                    f"AutoPTZ: ошибка continuous_move/stop при потере цели: {exc}"
                )
            return

        # ====== ЦЕЛЬ ВИДИМ ======
        h, w = frame_shape[:2]
        bbox = getattr(target, "bbox")
        cx, cy = self._bbox_center(bbox)

        cx_frame = w / 2.0
        cy_frame = h / 2.0

        # нормализованная ошибка ([-1..1])
        err_x = (cx - cx_frame) / max(1.0, cx_frame)
        err_y = (cy_frame - cy) / max(1.0, cy_frame)  # ось Y перевёрнута

        # производная ошибки (скорость цели в координатах кадра)
        derr_x = (err_x - self._prev_err_x) / dt
        derr_y = (err_y - self._prev_err_y) / dt
        derr_x = self._clamp(derr_x, -self._derr_limit, self._derr_limit)
        derr_y = self._clamp(derr_y, -self._derr_limit, self._derr_limit)

        self._prev_err_x = err_x
        self._prev_err_y = err_y

        # lookahead: целимся чуть вперёд, компенсируя задержку
        err_x_pred = err_x + derr_x * self._lead_time
        err_y_pred = err_y + derr_y * self._lead_time

        # dead zone применяем к предсказанной ошибке
        if abs(err_x_pred) < self.dead_zone:
            err_x_pred = 0.0
        if abs(err_y_pred) < self.dead_zone:
            err_y_pred = 0.0

        # scale: не даём ему слишком душить скорость (особенно при большом bbox),
        # а если ошибка большая — вообще отключаем "душилку"
        scale = self._zoom_scale(bbox, frame_shape)
        scale = max(scale, self._scale_min)
        if (
            abs(err_x_pred) > self._scale_override_err
            or abs(err_y_pred) > self._scale_override_err
        ):
            scale = 1.0

        # PD-регулятор
        vx_raw = (self.kp_pan * err_x_pred + self._kd_pan * derr_x) * scale
        vy_raw = (self.kp_tilt * err_y_pred + self._kd_tilt * derr_y) * scale

        vx = self._error_to_speed(vx_raw)
        vy = self._error_to_speed(vy_raw)

        # сглаживание команд (уменьшает дрожание, но сохраняет реакцию)
        a = self._cmd_smooth
        self._cmd_vx = a * self._cmd_vx + (1.0 - a) * vx
        self._cmd_vy = a * self._cmd_vy + (1.0 - a) * vy

        try:
            if (
                abs(self._cmd_vx) < self.min_speed
                and abs(self._cmd_vy) < self.min_speed
            ):
                self._controller.stop(pan_tilt=True, zoom=False)
            else:
                self._controller.continuous_move(self._cmd_vx, self._cmd_vy, zoom=0.0)
        except Exception as exc:
            logger.exception(f"AutoPTZ: ошибка continuous_move/stop: {exc}")
