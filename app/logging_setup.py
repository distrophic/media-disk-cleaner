"""Технический лог приложения в каталоге пользовательских данных."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.paths import ensure_user_dirs, technical_log_path

_LOGGER_NAME = "media_disk_cleaner"
_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    ensure_user_dirs()
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    log_path = technical_log_path()
    already = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(log_path)
        for handler in logger.handlers
    )
    if already:
        return
    handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logging.getLogger(_LOGGER_NAME).info("Logging started: %s", log_path)
