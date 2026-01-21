import pytest
from app.core.tracking.centroid_tracker import CentroidTracker
from app.core.detection.yolo_detector import Detection


class TestCentroidTracker:
    """Тесты для CentroidTracker."""
    
    def test_initialization(self):
        """Проверяет инициализацию трекера."""
        tracker = CentroidTracker()
        assert tracker._next_id == 1
        assert len(tracker._tracks) == 0
    
    def test_register_new_detection(self):
        """Проверяет регистрацию новой детекции."""
        tracker = CentroidTracker()
        det = Detection(bbox=(10, 10, 50, 50), cls_id=0, conf=0.9)
        
        result = tracker.update([det])
        
        assert len(result) == 1
        assert result[0].track_id == 1
    
    def test_track_reuse_same_object(self):
        """Проверяет переиспользование track_id для одного объекта."""
        tracker = CentroidTracker()
        
        # Первый кадр
        det1 = Detection(bbox=(10, 10, 50, 50), cls_id=0, conf=0.9)
        result1 = tracker.update([det1])
        track_id1 = result1[0].track_id
        
        # Второй кадр - объект немного двинулся
        det2 = Detection(bbox=(12, 12, 52, 52), cls_id=0, conf=0.9)
        result2 = tracker.update([det2])
        track_id2 = result2[0].track_id
        
        assert track_id1 == track_id2
    
    def test_empty_detections(self):
        """Проверяет обработку пустого списка детекций."""
        tracker = CentroidTracker()
        
        det = Detection(bbox=(10, 10, 50, 50), cls_id=0, conf=0.9)
        tracker.update([det])
        
        # Кадр без детекций
        result = tracker.update([])
        
        assert len(result) == 0
    
    def test_object_disappears_after_max_disappeared(self):
        """Проверяет удаление объекта при долгом отсутствии."""
        tracker = CentroidTracker(max_disappeared=3)
        
        # Регистрируем объект
        det = Detection(bbox=(10, 10, 50, 50), cls_id=0, conf=0.9)
        result = tracker.update([det])
        track_id = result[0].track_id
        
        # Теряем объект на 4 кадра (больше max_disappeared)
        for _ in range(4):
            tracker.update([])
        
        # Объект должен быть удален
        assert track_id not in tracker._tracks