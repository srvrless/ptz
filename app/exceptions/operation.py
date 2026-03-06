from .base import AppError


class OperationError(AppError):
    """Базовое исключение для ошибок операций."""

    status_code: int = 400
    error_code: str = "operation_error"

    def __init__(self, message: str):
        super().__init__(message)


class PTZMoveError(OperationError):
    """Исключение, возникающее при ошибке перемещения PTZ камеры."""

    error_code: str = "ptz_move_error"

    def __init__(self, camera_id: str, reason: str):
        message = f"Failed to move PTZ camera with ID '{camera_id}': {reason}."
        super().__init__(message)
