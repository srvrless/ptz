from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math

from app.core.detection.yolo_detector import Detection


@dataclass
class _Track:
    object_id: int
    bbox: Tuple[int, int, int, int]
    disappeared: int = 0


class CentroidTracker:
    """
    Очень простой трекер по центроидам.
    Использует евклидово расстояние между центрами боксов.
    """

    def __init__(self, max_distance: float = 80.0, max_disappeared: int = 10) -> None:
        self._next_id: int = 1
        self._max_distance = max_distance
        self._max_disappeared = max_disappeared
        self._tracks: Dict[int, _Track] = {}

    @staticmethod
    def _centroid(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _register(self, det: Detection) -> int:
        oid = self._next_id
        self._next_id += 1
        self._tracks[oid] = _Track(object_id=oid, bbox=det.bbox, disappeared=0)
        return oid

    def _deregister(self, object_id: int) -> None:
        self._tracks.pop(object_id, None)

    def update(self, detections: List[Detection]) -> List[Detection]:
        """
        На вход — список детекций за кадр.
        На выходе — те же объекты, но с заполненным .track_id.
        """
        # нет активных треков — всё новое
        if len(self._tracks) == 0:
            for d in detections:
                d.track_id = self._register(d)
            return detections

        # в кадре никого нет — увеличиваем disappeared
        if len(detections) == 0:
            to_delete = []
            for oid, track in self._tracks.items():
                track.disappeared += 1
                if track.disappeared > self._max_disappeared:
                    to_delete.append(oid)
            for oid in to_delete:
                self._deregister(oid)
            return []

        track_ids = list(self._tracks.keys())
        track_centroids = [self._centroid(self._tracks[oid].bbox) for oid in track_ids]
        det_centroids = [self._centroid(d.bbox) for d in detections]

        used_tracks = set()
        used_dets = set()

        # жадный матчинг: для каждой детекции — ближайший свободный трек
        for det_idx, det_c in enumerate(det_centroids):
            best_oid = None
            best_dist = float("inf")

            for oid, tr_c in zip(track_ids, track_centroids):
                if oid in used_tracks:
                    continue
                dist = math.hypot(det_c[0] - tr_c[0], det_c[1] - tr_c[1])
                if dist < best_dist:
                    best_dist = dist
                    best_oid = oid

            if best_oid is not None and best_dist <= self._max_distance:
                used_tracks.add(best_oid)
                used_dets.add(det_idx)
                track = self._tracks[best_oid]
                track.bbox = detections[det_idx].bbox
                track.disappeared = 0
                detections[det_idx].track_id = best_oid

        # новые объекты — не сматченные детекции
        for det_idx, det in enumerate(detections):
            if det_idx in used_dets:
                continue
            det.track_id = self._register(det)

        # треки, которые остались без детекции
        for oid, track in list(self._tracks.items()):
            if oid in used_tracks:
                continue
            track.disappeared += 1
            if track.disappeared > self._max_disappeared:
                self._deregister(oid)

        return detections
