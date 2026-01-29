from .base import AppError


class ValidationError(AppError):
    """Базовое исключение для ошибок валидации данных."""
    status_code: int = 400
    error_code: str = "validation_error"

    def __init__(self, message: str):
        super().__init__(message)


class InvalidRadarIDError(ValidationError):
    """Исключение, возникающее при передаче некорректного ID радара."""
    error_code: str = "invalid_radar_id"

    def __init__(self, radar_id: str):
        message = f"Invalid radar ID: '{radar_id}'."
        super().__init__(message)