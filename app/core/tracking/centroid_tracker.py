from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.core.detection.yolo_detector import Detection


@dataclass
class _Track:
    object_id: int
    bbox: Tuple[int, int, int, int]
    disappeared: int = 0

    # стабильность трека
    hits: int = 0  # сколько раз подряд/всего успешно сматчился
    age: int = 0  # сколько кадров живёт

    # простая модель движения (constant velocity)
    vx: float = 0.0
    vy: float = 0.0
    last_centroid: Optional[Tuple[float, float]] = None


class CentroidTracker:
    """
    Улучшенный centroid-трекер:
    - предсказание положения по скорости (vx, vy)
    - матчинг по комбинированной метрике IoU + distance
    - глобально-жадное сопоставление (по всем парам с сортировкой)
    - лёгкая компенсация движения камеры (медианный сдвиг по матчам)
    """

    def __init__(
        self,
        max_distance: float = 80.0,
        max_disappeared: int = 20,
        iou_weight: float = 0.6,  # 0..1: чем больше, тем важнее IoU
        min_iou: float = 0.05,  # отсечка (очень мягкая)
        max_cost: float = 1.2,  # отсечка по суммарной "плохости" пары
        vel_smooth: float = 0.7,  # сглаживание скорости (0..1)
        cam_smooth: float = 0.8,  # сглаживание компенсации камеры (0..1)
    ) -> None:
        self._next_id: int = 1
        self._max_distance = float(max_distance)
        self._max_disappeared = int(max_disappeared)

        self._iou_weight = float(iou_weight)
        self._min_iou = float(min_iou)
        self._max_cost = float(max_cost)
        self._vel_smooth = float(vel_smooth)
        self._cam_smooth = float(cam_smooth)

        self._tracks: Dict[int, _Track] = {}

        self._cam_dx: float = 0.0
        self._cam_dy: float = 0.0

    def reset(self) -> None:
        """Сброс всех треков (например, при переключении видеопотока)."""
        self._tracks.clear()
        self._next_id = 1
        self._cam_dx = 0.0
        self._cam_dy = 0.0

    @staticmethod
    def _centroid(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @staticmethod
    def _shift_bbox(
        bbox: Tuple[int, int, int, int], dx: float, dy: float
    ) -> Tuple[int, int, int, int]:
        x1, y1, x2, y2 = bbox
        return (
            int(round(x1 + dx)),
            int(round(y1 + dy)),
            int(round(x2 + dx)),
            int(round(y2 + dy)),
        )

    @staticmethod
    def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)

        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0

        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        denom = area_a + area_b - inter
        return float(inter / denom) if denom > 0 else 0.0

    def _register(self, det: Detection) -> int:
        oid = self._next_id
        self._next_id += 1
        tr = _Track(object_id=oid, bbox=det.bbox, disappeared=0, hits=1, age=1)
        tr.last_centroid = self._centroid(det.bbox)
        self._tracks[oid] = tr
        return oid

    def _deregister(self, object_id: int) -> None:
        self._tracks.pop(object_id, None)

    def update(self, detections: List[Detection]) -> List[Detection]:
        # 1) нет треков — всё новое
        if not self._tracks:
            for d in detections:
                d.track_id = self._register(d)
            return detections

        # 2) нет детекций — увеличиваем disappeared
        if not detections:
            to_delete = []
            for oid, tr in self._tracks.items():
                tr.age += 1
                tr.disappeared += 1
                if tr.disappeared > self._max_disappeared:
                    to_delete.append(oid)
            for oid in to_delete:
                self._deregister(oid)
            return []

        # подготовка
        track_ids = list(self._tracks.keys())
        det_centroids = [self._centroid(d.bbox) for d in detections]

        # 3) предсказываем положение треков (скорость + компенсация камеры)
        pred_bboxes: List[Tuple[int, int, int, int]] = []
        pred_centroids: List[Tuple[float, float]] = []
        for oid in track_ids:
            tr = self._tracks[oid]
            tr.age += 1

            # если впервые — last_centroid уже есть после _register, но на всякий случай
            cur_cx, cur_cy = tr.last_centroid or self._centroid(tr.bbox)

            # pred = last + v + camera_shift
            dx = tr.vx + self._cam_dx
            dy = tr.vy + self._cam_dy

            pb = self._shift_bbox(tr.bbox, dx, dy)
            pc = self._centroid(pb)
            pred_bboxes.append(pb)
            pred_centroids.append(pc)

        # 4) строим список всех пар (track, det) с cost = w*(1-iou) + (1-w)*norm_dist
        pairs: List[
            Tuple[float, int, int, float, float]
        ] = []  # (cost, t_idx, d_idx, iou, dist)
        for t_idx, oid in enumerate(track_ids):
            pb = pred_bboxes[t_idx]
            pc = pred_centroids[t_idx]
            for d_idx, det in enumerate(detections):
                iou = self._iou(pb, det.bbox)
                dc = det_centroids[d_idx]
                dist = math.hypot(pc[0] - dc[0], pc[1] - dc[1])

                norm_dist = dist / max(1e-6, self._max_distance)
                cost = (
                    self._iou_weight * (1.0 - iou)
                    + (1.0 - self._iou_weight) * norm_dist
                )

                # мягкие гейты (чтобы не разваливалось на поворотах камеры)
                if iou < self._min_iou and dist > self._max_distance * 1.5:
                    continue
                if cost > self._max_cost:
                    continue

                pairs.append((cost, t_idx, d_idx, iou, dist))

        pairs.sort(key=lambda x: x[0])

        used_t = set()
        used_d = set()
        matches: List[Tuple[int, int, float]] = []  # (t_idx, d_idx, iou)

        for cost, t_idx, d_idx, iou, dist in pairs:
            if t_idx in used_t or d_idx in used_d:
                continue
            used_t.add(t_idx)
            used_d.add(d_idx)
            matches.append((t_idx, d_idx, iou))

        # 5) обновляем сматченные треки + собираем сдвиг камеры по residual
        cam_res_dx = []
        cam_res_dy = []

        for t_idx, d_idx, iou in matches:
            oid = track_ids[t_idx]
            tr = self._tracks[oid]
            det = detections[d_idx]

            old_cx, old_cy = tr.last_centroid or self._centroid(tr.bbox)
            new_cx, new_cy = det_centroids[d_idx]

            # скорость объекта (между кадрами). Камера тоже входит — мы позже её оценим и сгладим.
            inst_vx = new_cx - old_cx
            inst_vy = new_cy - old_cy
            tr.vx = self._vel_smooth * tr.vx + (1.0 - self._vel_smooth) * inst_vx
            tr.vy = self._vel_smooth * tr.vy + (1.0 - self._vel_smooth) * inst_vy

            # апдейт трека
            tr.bbox = det.bbox
            tr.last_centroid = (new_cx, new_cy)
            tr.disappeared = 0
            tr.hits += 1

            det.track_id = oid

            # residual камеры: насколько детекция ушла от "last + v" (берём только хорошие совпадения)
            if iou >= 0.2:
                pred_no_cam_x = old_cx + tr.vx
                pred_no_cam_y = old_cy + tr.vy
                cam_res_dx.append(new_cx - pred_no_cam_x)
                cam_res_dy.append(new_cy - pred_no_cam_y)

        # сглаженно обновляем компенсацию камеры
        if len(cam_res_dx) >= 3:
            mdx = statistics.median(cam_res_dx)
            mdy = statistics.median(cam_res_dy)
            self._cam_dx = (
                self._cam_smooth * self._cam_dx + (1.0 - self._cam_smooth) * mdx
            )
            self._cam_dy = (
                self._cam_smooth * self._cam_dy + (1.0 - self._cam_smooth) * mdy
            )
        else:
            # чуть затухаем, чтобы не "залипало"
            self._cam_dx *= 0.9
            self._cam_dy *= 0.9

        # 6) несматченные детекции — новые треки
        for d_idx, det in enumerate(detections):
            if d_idx in used_d:
                continue
            det.track_id = self._register(det)

        # 7) несматченные треки — увеличиваем disappeared, удаляем при превышении
        for t_idx, oid in enumerate(track_ids):
            if t_idx in used_t:
                continue
            tr = self._tracks.get(oid)
            if not tr:
                continue
            tr.disappeared += 1
            # слегка затухаем скорость, пока объект "потерян"
            tr.vx *= 0.8
            tr.vy *= 0.8
            if tr.disappeared > self._max_disappeared:
                self._deregister(oid)

        return detections
