# app/api/v1/detector.py

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaSyncRoute
from fastapi import APIRouter, HTTPException

from app.config.settings import DetectorMode
from app.core.detection.yolo_detector import DetectorManager
from app.schemas.detector import (
    DetectorModeRequest,
    DetectorModeResponse,
    DetectorStatusResponse,
)

router = APIRouter(
    prefix="/api/detector", tags=["detector"], route_class=DishkaSyncRoute
)


@router.get("/status", response_model=DetectorStatusResponse)
def get_detector_status(
    detector_manager: FromDishka[DetectorManager],
):
    """
    Получить текущий статус детектора.
    Возвращает текущий режим и доступные режимы с информацией о весах.
    """
    current_mode = detector_manager.get_current_mode()
    return DetectorStatusResponse(
        current_mode=current_mode.value if current_mode else None,
        available_modes=detector_manager.get_available_modes(),
    )


@router.post("/mode", response_model=DetectorModeResponse)
def switch_detector_mode(
    request: DetectorModeRequest,
    detector_manager: FromDishka[DetectorManager],
):
    """
    Переключить режим детектора между optical и thermal.

    Переключение происходит «на лету» — текущая модель выгружается,
    новая загружается. GPU память освобождается корректно.

    Потоки детекции автоматически начнут использовать новый детектор.
    """
    available = detector_manager.get_available_modes()
    mode_info = available.get(request.mode.value)

    if not mode_info or not mode_info["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Weights for {request.mode.value} mode not found: "
            f"{mode_info['weights_path'] if mode_info else 'unknown'}",
        )

    try:
        new_mode = detector_manager.switch_mode(request.mode)
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
def switch_to_optical(
    detector_manager: FromDishka[DetectorManager],
):
    """Быстрое переключение на оптический режим."""
    return switch_detector_mode(
        DetectorModeRequest(mode=DetectorMode.OPTICAL),
        detector_manager,
    )


@router.post("/mode/thermal", response_model=DetectorModeResponse)
def switch_to_thermal(
    detector_manager: FromDishka[DetectorManager],
):
    """Быстрое переключение на тепловизионный режим."""
    return switch_detector_mode(
        DetectorModeRequest(mode=DetectorMode.THERMAL),
        detector_manager,
    )
