import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"


def get_logger(name: str) -> logging.Logger:
    """
    Создаёт отдельный логгер для модуля с ротацией файлов и выводом в консоль.
    :param name: имя модуля (например, 'api', 'camera')
    :return: настроенный logger
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        DIR = f"{LOG_DIR}/{name}.logs/"
        os.makedirs(DIR, exist_ok=True)
        log_path = os.path.join(DIR, f"{name}.log")

        handler = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Добавляем вывод в консоль
        # console_handler = logging.StreamHandler()
        # console_handler.setFormatter(formatter)
        # logger.addHandler(console_handler)

        logger.propagate = False

    return logger
