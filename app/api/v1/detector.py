# app/api/v1/detector.py

from app.schemas.detector import DetectorModeRequest, DetectorModeResponse, DetectorStatusResponse
from fastapi import APIRouter, HTTPException

from app.config.settings import DetectorMode
from app.core.detection.yolo_detector import get_detector_manager

router = APIRouter(prefix="/api/detector", tags=["detector"])




@router.get("/status", response_model=DetectorStatusResponse)
def get_detector_status():
    """
    Получить текущий статус детектора.
    Возвращает текущий режим и доступные режимы с информацией о весах.
    """
    manager = get_detector_manager()
    current_mode = manager.get_current_mode()

    return DetectorStatusResponse(
        current_mode=current_mode.value if current_mode else None,
        available_modes=manager.get_available_modes(),
    )


@router.post("/mode", response_model=DetectorModeResponse)
def switch_detector_mode(request: DetectorModeRequest):
    """
    Переключить режим детектора между optical и thermal.

    Переключение происходит «на лету» — текущая модель выгружается,
    новая загружается. GPU память освобождается корректно.

    Потоки детекции автоматически начнут использовать новый детектор.
    """
    manager = get_detector_manager()

    # Проверяем доступность весов для запрошенного режима
    available = manager.get_available_modes()
    mode_info = available.get(request.mode.value)

    if not mode_info or not mode_info["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Weights for {request.mode.value} mode not found: "
            f"{mode_info['weights_path'] if mode_info else 'unknown'}",
        )

    try:
        new_mode = manager.switch_mode(request.mode)
        return DetectorModeResponse(
            current_mode=new_mode.value,
            message=f"Detector switched to {new_mode.value} mode",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to switch detector mode: {e}"
        )


@router.post("/mode/optical", response_model=DetectorModeResponse)
def switch_to_optical():
    """Быстрое переключение на оптический режим."""
    return switch_detector_mode(DetectorModeRequest(mode=DetectorMode.OPTICAL))


@router.post("/mode/thermal", response_model=DetectorModeResponse)
def switch_to_thermal():
    """Быстрое переключение на тепловизионный режим."""
    return switch_detector_mode(DetectorModeRequest(mode=DetectorMode.THERMAL))
