from .base import AppError


class NotFoundError(AppError):
    """Базовое исключение 404 ошибок"""
    status_code: int = 404
    error_code: str = "not_found"

    def __init__(self, message: str = "Ресурс не найден"):
        super().__init__(message)


class CameraNotFoundError(NotFoundError):
    """Исключение, возникающее при попытке доступа к несуществующей камере."""
    error_code: str = "camera_not_found"

    def __init__(self, camera_id: str):
        message = f"Camera with ID '{camera_id}' not found."
        super().__init__(message)


class PTZControllerNotFoundError(NotFoundError):
    """Исключение, возникающее при попытке доступа к несуществующему PTZ контроллеру."""
    error_code: str = "ptz_controller_not_found"

    def __init__(self, controller_id: str):
        message = f"PTZ Controller with ID '{controller_id}' not found."
        super().__init__(message)