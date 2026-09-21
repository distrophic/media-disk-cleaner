"""Фоновый запуск сканера без блокировки GUI.

Сканер выполняется в QRunnable. Поток нельзя аварийно terminate():
отмена — только через threading.Event, который сканер проверяет в цикле.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from core.scanner import ScanOptions, Scanner, ScanProgress
from models.media_file import MediaFile

logger = logging.getLogger("media_disk_cleaner.scan_worker")


class ScanSignals(QObject):
    """Сигналы, безопасные для соединения со слотами главного потока Qt."""

    batch_ready = Signal(object)
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)


class ScanWorker(QRunnable):
    """QRunnable-обёртка над ``Scanner.scan``.

    Не удаляет файлы. Не обходит файловую систему самостоятельно.
    """

    def __init__(
        self,
        roots: Sequence[Path],
        *,
        options: ScanOptions | None = None,
        scanner: Scanner | None = None,
        user_home: Path | None = None,
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.signals = ScanSignals()
        self._roots = [Path(root) for root in roots]
        self._options = options if options is not None else ScanOptions()
        self._scanner = scanner if scanner is not None else Scanner()
        self._user_home = user_home
        self._cancel_event = threading.Event()
        self._started = False

    def cancel(self) -> None:
        """Кооперативная отмена. Не вызывает terminate() потока."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def run(self) -> None:
        if self._started:
            logger.warning("ScanWorker.run called more than once")
            return
        self._started = True
        try:
            result = self._scanner.scan(
                self._roots,
                options=self._options,
                cancel_event=self._cancel_event,
                on_batch=self._emit_batch,
                on_progress=self._emit_progress,
                user_home=self._user_home,
            )
        except Exception as exc:
            logger.exception("Scan worker failed")
            self.signals.failed.emit(f"{exc.__class__.__name__}: {exc}")
            return
        self.signals.finished.emit(result)

    def _emit_batch(self, batch: list[MediaFile]) -> None:
        self.signals.batch_ready.emit(batch)

    def _emit_progress(self, progress: ScanProgress) -> None:
        self.signals.progress.emit(progress)
