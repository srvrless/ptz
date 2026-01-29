class AppError(Exception):
    """Базовый класс для всех пользовательских исключений в приложении."""
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)