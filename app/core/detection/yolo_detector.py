import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch

from logger.setup_logger import get_logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Перенаправляем в локальную папку проекта до импорта YOLO.
YOLO_CONFIG_ROOT = PROJECT_ROOT / "logs"
os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_ROOT))
(YOLO_CONFIG_ROOT / "Ultralytics").mkdir(parents=True, exist_ok=True)

from ultralytics import YOLO  # noqa: E402

logger = get_logger("object_detector")


@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]
    cls_id: int
    conf: float
    track_id: Optional[int] = None
    name: Optional[str] = None

    def to_dict(self) -> dict:
        x1, y1, x2, y2 = self.bbox
        return {
            "id": self.track_id,
            "name": self.name or "",
            "confidence": round(self.conf, 4),
            "bbox": [x1, y1, x2, y2],
        }


class ObjectDetector:
    """Обёртка над Ultralytics YOLO для нанесения боксов на кадр."""

    def __init__(
        self,
        weights_path: Optional[str | Path] = None,
        conf: float = 0.3,
        device: Optional[str] = None,
        img_size: int = 640,
    ) -> None:
        self.weights_path = (
            Path(weights_path) if weights_path else PROJECT_ROOT / "best.pt"
        )
        if not self.weights_path.exists():
            raise FileNotFoundError(f"Weights not found: {self.weights_path}")

        self.conf = conf
        self.device = device or self._select_device()
        self.lock = Lock()
        self.img_size = img_size

        try:
            self.model = YOLO(str(self.weights_path))
            if self.device:
                self.model.to(self.device)
            self.names = self.model.names
            logger.info(
                f"Loaded detection model from {self.weights_path} on {self.device}"
            )
        except Exception as exc:
            logger.error(f"Failed to load model: {exc}")
            raise

    def _select_device(self) -> str:
        """Выбирает доступное устройство: env > CUDA > XPU > CPU."""
        env_device = os.getenv("DETECTOR_DEVICE")
        if env_device:
            return env_device
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch, "xpu") and torch.xpu.is_available():  # Intel GPU
            return "xpu"
        return "cpu"

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Выполнить детекцию и вернуть список Detetion без рисования.
        """
        if frame is None:
            return []

        try:
            with self.lock:
                results = self.model.predict(
                    frame,
                    verbose=False,
                    conf=self.conf,
                    device=self.device,
                    imgsz=self.img_size,
                )
        except Exception as exc:
            logger.error(f"Detection failed: {exc}")
            return []

        if not results:
            return []

        boxes = results[0].boxes
        if boxes is None:
            return []

        detections: List[Detection] = []
        names = self.names or {}
        for xyxy, cls_id, det_conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
            x1, y1, x2, y2 = [int(x) for x in xyxy]
            class_name = names.get(int(cls_id), str(int(cls_id)))

            detections.append(
                Detection(
                    bbox=(x1, y1, x2, y2),
                    cls_id=int(cls_id),
                    conf=float(det_conf),
                    name=class_name,
                )
            )
        return detections

    def draw(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """
        Нарисовать боксы и подписи (с учётом track_id) на кадре.
        """
        if frame is None:
            return frame

        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            class_name = det.name or str(det.cls_id)
            id_prefix = f"#{det.track_id} " if det.track_id is not None else ""
            label = f"{id_prefix}{class_name} {det.conf:.2f}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                label,
                (x1, max(y1 - 10, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        return annotated

    def annotate_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Обратная совместимость: просто детекция + рисование без трекинга.
        """
        detections = self.detect(frame)
        return self.draw(frame, detections)


# --- ленивый синглтон детектора ---

_detector: Optional[ObjectDetector] = None


def get_detector() -> ObjectDetector:
    """
    Возвращает синглтон детектора, чтобы не грузить веса каждый запрос.
    Бросит исключение, если не удалось инициализировать.
    """
    global _detector
    if _detector is None:
        _detector = ObjectDetector()
    return _detector
