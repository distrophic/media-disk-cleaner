"""Сборка приложения и точка запуска GUI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.constants import APP_ID, APP_NAME, APP_VERSION
from app.logging_setup import configure_logging
from app.paths import ensure_user_dirs, is_frozen, resource_root
from core.journal_service import JournalService
from ui.main_window import MainWindow


def _prepare_frozen_qt() -> None:
    """Плагины Qt из каталога сборки. Не пишет файлы в sys._MEIPASS."""
    if not is_frozen():
        return
    root = resource_root()
    for relative in ("PySide6/plugins", "plugins"):
        plugins = root / relative
        if plugins.is_dir():
            os.environ.setdefault("QT_PLUGIN_PATH", str(plugins))
            break


def run(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv if argv is None else argv)
    _prepare_frozen_qt()
    ensure_user_dirs()
    configure_logging()
    JournalService().append("app_start", "Приложение запущено")
    app = QApplication(arguments)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    window = MainWindow()
    window.showNormal()
    return int(app.exec())
