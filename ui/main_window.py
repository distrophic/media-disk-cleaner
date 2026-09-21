"""Главное окно Media Disk Cleaner."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QThreadPool, QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.constants import (
    APP_NAME,
    SCAN_MODE_EXTENDED,
    SCAN_MODE_QUICK,
    SCAN_MODE_SELECTIVE,
    WINDOW_BOTTOM_MARGIN_MIN,
    WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_EDGE_MARGIN_MIN,
    WINDOW_HEIGHT_RATIO,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_WIDTH_RATIO,
)
from app.paths import logs_dir, reports_dir
from core.drive_service import DriveInfo, DriveService
from core.journal_service import JournalService
from core.metadata_service import MediaPreview, MetadataService
from core.recycle_service import RecycleReport, RecycleService
from core.report_service import ReportService
from core.scanner import ScanOptions, ScanProgress, get_quick_scan_roots, is_drive_root
from core.scan_worker import ScanWorker
from models.media_file import MediaFile
from models.media_table_model import MediaTableModel, format_size_bytes
from models.scan_result import ScanResult
from ui.confirmation_dialog import RecycleConfirmationDialog
from ui.dashboard_widget import DashboardWidget
from ui.journal_widget import JournalWidget
from ui.message_box import ask_ok_cancel, ask_yes_no, show_info, show_warning
from ui.preview_widget import PreviewWidget
from ui.preview_worker import PreviewSignals, PreviewWorker
from ui.results_widget import ResultsWidget
from ui.scan_widget import ScanWidget
from ui.styles import theme_qss

NAV_OVERVIEW = 0
NAV_SCAN = 1
NAV_FILES = 2
NAV_PLACEHOLDER = 3
NAV_JOURNAL = 4


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(800, 500)
        self._startup_placed = False
        self._place_startup_window()
        self._dark = False
        self._drive_service = DriveService()
        self._model = MediaTableModel(self)
        self._pool = QThreadPool.globalInstance()
        self._worker: ScanWorker | None = None
        self._added_folders: list[Path] = []
        self._warned_drive_roots: set[str] = set()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(280)
        self._pending_search = ""
        self._stats_timer = QTimer(self)
        self._stats_timer.setSingleShot(True)
        self._stats_timer.setInterval(120)
        self._recycle = RecycleService()
        self._journal = JournalService()
        self._reports = ReportService()
        self._metadata = MetadataService()
        self._preview_signals = PreviewSignals(self)
        self._preview_request_id = 0
        self._pending_preview: MediaFile | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(140)
        self._build_ui()
        self._connect()
        self._refresh_drives()
        self._apply_theme()
        self._update_cards()
        self._update_bottom()
        self._update_filter_stats()
        self.statusBar().showMessage("Готово. Сканирование не запускается автоматически.")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("centralRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side_layout = QVBoxLayout(sidebar)
        brand = QLabel(APP_NAME)
        brand.setWordWrap(True)
        side_layout.addWidget(brand)
        self._nav = QListWidget()
        self._nav.setObjectName("navList")
        for title in (
            "Обзор",
            "Сканирование",
            "Все файлы",
            "Крупные файлы",
            "Дубликаты",
            "Корзина и журнал",
        ):
            self._nav.addItem(QListWidgetItem(title))
        self._nav.setCurrentRow(0)
        side_layout.addWidget(self._nav, 1)
        self._theme_button = QPushButton("Тёмная тема")
        self._theme_button.setObjectName("secondaryButton")
        side_layout.addWidget(self._theme_button)
        outer.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(16, 16, 16, 12)
        content.setSpacing(12)
        content.addLayout(self._build_toolbar())
        self._dashboard = DashboardWidget()
        content.addWidget(self._dashboard)
        self._filter_stats = QLabel("В таблице: 0 файлов / 0 Б")
        content.addWidget(self._filter_stats)
        self._size_hint = QLabel(
            "Карточки считают только найденные фото, видео и аудио. "
            "Это не занятое место на всём диске: игры, программы и прочие файлы сюда не входят."
        )
        self._size_hint.setWordWrap(True)
        content.addWidget(self._size_hint)
        self._stack = QStackedWidget()
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        self._drive_label = QLabel()
        self._drive_label.setWordWrap(True)
        overview_layout.addWidget(self._drive_label)
        overview_layout.addWidget(
            QLabel(
                "Выберите папки и нажмите «Начать сканирование». "
                "Файлы не удаляются автоматически и не выбираются сами."
            )
        )
        overview_layout.addStretch(1)
        self._scan_page = ScanWidget()
        self._results = ResultsWidget(self._model)
        self._placeholder = QLabel()
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._journal_page = JournalWidget(self._journal)
        self._stack.addWidget(overview)
        self._stack.addWidget(self._scan_page)
        self._stack.addWidget(self._results)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._journal_page)
        self._preview = PreviewWidget()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._stack)
        splitter.addWidget(self._preview)
        splitter.setChildrenCollapsible(False)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setOpaqueResize(True)
        splitter.setHandleWidth(6)
        self._stack.setMinimumWidth(420)
        self._stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self._preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 320])
        splitter.splitterMoved.connect(self._keep_preview_visible)
        self._splitter = splitter
        content.addWidget(splitter, 1)
        content.addLayout(self._build_bottom())
        holder = QWidget()
        holder.setLayout(content)
        outer.addWidget(holder, 1)
        self.setStatusBar(QStatusBar())

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self._drive_combo = QComboBox()
        self._drive_combo.setMinimumWidth(260)
        self._add_folder_button = QPushButton("Добавить папку")
        self._add_folder_button.setObjectName("secondaryButton")
        self._start_button = QPushButton("Начать сканирование")
        self._stop_button = QPushButton("Остановить")
        self._stop_button.setEnabled(False)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Поиск по имени или пути")
        self._search.setClearButtonEnabled(True)
        layout.addWidget(QLabel("Диск / папка"))
        layout.addWidget(self._drive_combo, 1)
        layout.addWidget(self._add_folder_button)
        layout.addWidget(self._start_button)
        layout.addWidget(self._stop_button)
        layout.addWidget(self._search, 1)
        return layout

    def _build_bottom(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self._selected_label = QLabel("Выбрано: 0 файлов / 0 Б")
        self._clear_button = QPushButton("Снять выделение")
        self._clear_button.setObjectName("secondaryButton")
        self._recycle_button = QPushButton("Переместить в корзину")
        self._recycle_button.setObjectName("dangerButton")
        self._recycle_button.setEnabled(False)
        self._recycle_button.setToolTip(
            "Перемещает только явно отмеченные файлы в корзину Windows после подтверждения."
        )
        layout.addWidget(self._selected_label)
        layout.addStretch(1)
        layout.addWidget(self._clear_button)
        layout.addWidget(self._recycle_button)
        folders_layout = QVBoxLayout()
        folders_layout.addWidget(QLabel("Выбранные папки"))
        self._folder_list = QListWidget()
        self._folder_list.setObjectName("folderList")
        self._folder_list.setMaximumHeight(90)
        folders_layout.addWidget(self._folder_list)
        wrapper = QHBoxLayout()
        wrapper.addLayout(layout, 2)
        wrapper.addLayout(folders_layout, 1)
        return wrapper

    def _connect(self) -> None:
        self._nav.currentRowChanged.connect(self._on_nav)
        self._theme_button.clicked.connect(self._toggle_theme)
        self._add_folder_button.clicked.connect(self._add_folder)
        self._start_button.clicked.connect(self._start_scan)
        self._stop_button.clicked.connect(self._stop_scan)
        self._clear_button.clicked.connect(self._model.clear_selection)
        self._recycle_button.clicked.connect(self._recycle_selected)
        self._model.selection_changed.connect(self._on_selection_changed)
        self._results.open_folder_requested.connect(self._open_folder)
        self._results.filters_changed.connect(self._schedule_filter_stats)
        self._results.current_file_changed.connect(self._on_current_file)
        self._journal_page.open_journal_requested.connect(self._open_journal_folder)
        self._journal_page.clear_journal_requested.connect(self._clear_journal)
        self._journal_page.export_report_requested.connect(self._export_report)
        self._preview_timer.timeout.connect(self._load_preview)
        self._preview_signals.ready.connect(self._on_preview_ready)
        self._drive_combo.currentIndexChanged.connect(self._on_drive_chosen)
        self._search.textChanged.connect(self._on_search)
        self._search_timer.timeout.connect(self._apply_search)
        self._stats_timer.timeout.connect(self._update_filter_stats)

    def _apply_theme(self) -> None:
        qss = theme_qss(self._dark)
        # QSS только на содержимое окна. Если повесить его на QMainWindow,
        # системные QMessageBox раздуваются в почти пустое окно.
        central = self.centralWidget()
        if central is not None:
            central.setStyleSheet(qss)
        self.setStyleSheet("")
        if self._dark:
            self.statusBar().setStyleSheet(
                "QStatusBar, QStatusBar QLabel { background: #0f141e; color: #9aa7c2; }"
            )
        else:
            self.statusBar().setStyleSheet(
                "QStatusBar, QStatusBar QLabel { background: #e8edf5; color: #111827; }"
            )
        self._theme_button.setText("Светлая тема" if self._dark else "Тёмная тема")

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._apply_theme()

    def _refresh_drives(self) -> None:
        self._drive_combo.blockSignals(True)
        self._drive_combo.clear()
        self._drive_combo.addItem("Стандартные папки пользователя", None)
        for info in self._drive_service.list_target_drives():
            self._drive_combo.addItem(self._drive_item_text(info), info)
        self._drive_combo.blockSignals(False)
        self._update_drive_overview()

    def _drive_item_text(self, info: DriveInfo) -> str:
        if not info.available:
            return f"{info.letter} — недоступен"
        label = info.label or "без метки"
        free = format_size_bytes(info.free_bytes or 0)
        total = format_size_bytes(info.total_bytes or 0)
        return (
            f"{info.letter} {label} · {info.type_label_ru} · свободно {free} из {total}"
        )

    def _update_drive_overview(self) -> None:
        lines = []
        for info in self._drive_service.list_target_drives():
            if info.available:
                lines.append(
                    f"{info.letter} «{info.label or 'без метки'}»: "
                    f"тип {info.type_label_ru}, всего {format_size_bytes(info.total_bytes or 0)}, "
                    f"занято {format_size_bytes(info.used_bytes or 0)}, "
                    f"свободно {format_size_bytes(info.free_bytes or 0)}."
                )
            else:
                lines.append(f"{info.letter}: недоступен. Можно выбрать другую папку.")
        self._drive_label.setText("\n".join(lines))

    def _on_drive_chosen(self, index: int) -> None:
        info = self._drive_combo.itemData(index)
        if isinstance(info, DriveInfo) and not info.available:
            self.statusBar().showMessage(f"{info.letter} недоступен. Выберите другую папку.")
            return
        if isinstance(info, DriveInfo) and info.available:
            self.statusBar().showMessage(
                f"Выбран {info.letter}. Корень диска не сканируется автоматически."
            )

    def _on_nav(self, row: int) -> None:
        if row <= 1:
            self._stack.setCurrentIndex(row)
            return
        if row in (2, 3):
            self._stack.setCurrentIndex(NAV_FILES)
            self._results.apply_nav_preset(None, large_only=(row == 3))
            self._schedule_filter_stats()
            return
        if row == 5:
            self._journal_page.reload()
            self._stack.setCurrentIndex(NAV_JOURNAL)
            return
        self._placeholder.setText(
            "Поиск дубликатов — дополнительная функция следующих этапов."
        )
        self._stack.setCurrentIndex(NAV_PLACEHOLDER)

    def _on_search(self, text: str) -> None:
        self._pending_search = text
        self._search_timer.start()

    def _apply_search(self) -> None:
        self._results.table.setUpdatesEnabled(False)
        self._results.proxy.set_text(self._pending_search)
        self._results.table.setUpdatesEnabled(True)
        self._update_filter_stats()

    def _schedule_filter_stats(self) -> None:
        self._stats_timer.start()

    def _add_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Выберите папку для сканирования")
        if not selected:
            return
        path = Path(selected)
        if not self._confirm_drive_root(path):
            return
        self._append_folder(path)

    def _append_folder(self, path: Path) -> None:
        normalized = path
        for existing in self._added_folders:
            if existing == normalized:
                return
        self._added_folders.append(normalized)
        self._folder_list.addItem(str(normalized))

    def _confirm_drive_root(self, path: Path) -> bool:
        if not is_drive_root(path):
            return True
        key = str(path).casefold()
        if key in self._warned_drive_roots:
            return True
        text = (
            "Сканирование всего системного диска может занять много времени. "
            "Системные и защищённые папки будут автоматически пропущены. "
            "Программа не изменяет права доступа."
        )
        if path.drive.upper().rstrip("\\") != "C:":
            text = (
                "Сканирование корня диска может занять много времени. "
                "Системные и защищённые папки будут автоматически пропущены. "
                "Программа не изменяет права доступа."
            )
        if not ask_ok_cancel(self, "Предупреждение", text):
            return False
        self._warned_drive_roots.add(key)
        return True

    def _start_scan(self) -> None:
        if self._worker is not None:
            return
        mode = self._scan_page.current_mode()
        if mode == SCAN_MODE_EXTENDED:
            if not ask_ok_cancel(
                self,
                "Расширенное сканирование",
                "Расширенное сканирование не включается автоматически. "
                "Будут пропущены системные каталоги, ссылки и профили других "
                "пользователей, если они не выбраны явно. Продолжить?",
            ):
                return
        roots = self._resolve_roots(mode)
        if not roots:
            show_info(
                self,
                "Нет папок",
                "Добавьте папку или используйте быстрое сканирование стандартных каталогов.",
            )
            return
        if any(is_drive_root(root) for root in roots) and not all(
            self._confirm_drive_root(root) for root in roots if is_drive_root(root)
        ):
            return
        self._model.clear()
        self._preview.clear()
        self._results.filters.reset()
        self._search.clear()
        self._scan_page.reset_progress()
        self._scan_page.set_busy(True)
        self._results.set_scanning(True)
        self._update_cards()
        self._update_filter_stats()
        options = ScanOptions(mode=mode)
        worker = ScanWorker(roots, options=options)
        worker.signals.batch_ready.connect(self._on_batch)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_finished)
        worker.signals.failed.connect(self._on_failed)
        self._worker = worker
        self._start_button.setEnabled(False)
        self._stop_button.setEnabled(True)
        self._add_folder_button.setEnabled(False)
        self._recycle_button.setEnabled(False)
        self.statusBar().showMessage("Сканирование…")
        self._journal.append(
            "scan_start",
            "Начато сканирование",
            {
                "mode": mode,
                "roots": [str(root) for root in roots],
            },
        )
        self._pool.start(worker)

    def _resolve_roots(self, mode: str) -> list[Path]:
        if mode == SCAN_MODE_QUICK:
            return get_quick_scan_roots()
        if self._added_folders:
            return list(self._added_folders)
        info = self._drive_combo.currentData()
        if isinstance(info, DriveInfo) and info.available:
            if mode in {SCAN_MODE_SELECTIVE, SCAN_MODE_EXTENDED}:
                return [info.root_path]
        return []

    def _stop_scan(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.statusBar().showMessage("Остановка сканирования…")
            self._journal.append("scan_cancel", "Запрошена остановка сканирования")

    def _on_batch(self, batch: object) -> None:
        if isinstance(batch, list):
            files = [item for item in batch if isinstance(item, MediaFile)]
            self._model.append_files(files)
            self._update_cards()

    def _on_progress(self, progress: object) -> None:
        if isinstance(progress, ScanProgress):
            self._scan_page.show_progress(progress)
            self.statusBar().showMessage(
                f"Сканирование: {progress.current_folder} · найдено {progress.media_found}"
            )

    def _on_finished(self, result: object) -> None:
        self._release_worker()
        extra = ""
        if isinstance(result, ScanResult):
            extra = (
                f"Найдено {result.summary.files_found}, "
                f"ошибок доступа {result.summary.access_errors}."
            )
            if result.summary.cancelled:
                extra = "Сканирование остановлено. " + extra
            self._journal.append(
                "scan_finish",
                extra or "Сканирование завершено.",
                {
                    "files_found": result.summary.files_found,
                    "total_size_bytes": result.summary.total_size_bytes,
                    "skipped_directories": result.summary.skipped_directories,
                    "skipped_files": result.summary.skipped_files,
                    "access_errors": result.summary.access_errors,
                    "cancelled": result.summary.cancelled,
                    "mode": result.mode,
                    "roots": [str(root) for root in result.roots],
                },
            )
        self.statusBar().showMessage(extra or "Сканирование завершено.")
        self._update_cards()
        self._update_filter_stats()
        self._results.refresh_extensions()
        self._stack.setCurrentIndex(NAV_FILES)
        self._nav.setCurrentRow(2)

    def _on_failed(self, message: object) -> None:
        self._release_worker()
        show_warning(self, "Ошибка сканирования", str(message))
        self.statusBar().showMessage("Сканирование прервано из-за ошибки.")
        self._journal.append("scan_fail", "Ошибка сканирования", {"error": str(message)})

    def _release_worker(self) -> None:
        self._worker = None
        self._scan_page.set_busy(False)
        self._results.set_scanning(False)
        self._start_button.setEnabled(True)
        self._stop_button.setEnabled(False)
        self._add_folder_button.setEnabled(True)
        self._update_bottom()

    def _on_selection_changed(self) -> None:
        self._update_cards()
        self._update_bottom()
        self._schedule_filter_stats()

    def _update_cards(self) -> None:
        count, total, image_size, video_size, audio_size, selected = self._model.totals()
        self._dashboard.update_from_totals(
            count, total, image_size, video_size, audio_size, selected
        )

    def _update_filter_stats(self) -> None:
        visible, total, image_size, video_size, audio_size, selected = (
            self._results.proxy.visible_totals()
        )
        self._filter_stats.setText(
            "В таблице: "
            f"{visible} файлов / {format_size_bytes(total)} · "
            f"изобр. {format_size_bytes(image_size)} · "
            f"видео {format_size_bytes(video_size)} · "
            f"аудио {format_size_bytes(audio_size)} · "
            f"выбрано среди видимых {format_size_bytes(selected)}"
        )

    def _update_bottom(self) -> None:
        count = self._model.selected_count()
        size = self._model.selected_size_bytes()
        self._selected_label.setText(
            f"Выбрано: {count} файлов / {format_size_bytes(size)}"
        )
        scanning = self._worker is not None
        self._recycle_button.setEnabled(count > 0 and not scanning)

    def _recycle_selected(self) -> None:
        if self._worker is not None:
            return
        selected = self._model.selected_files()
        if not selected:
            return
        dialog = RecycleConfirmationDialog(selected, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        report = self._recycle.recycle_selected(selected)
        if report.moved_paths:
            self._model.remove_by_paths(report.moved_paths)
            self._results.refresh_extensions()
            self._schedule_preview(self._results.current_file())
        self._update_cards()
        self._update_bottom()
        self._update_filter_stats()
        self._log_recycle(report)
        show_info(
            self,
            "Результат",
            (
                f"Перемещено в корзину: {report.moved}\n"
                f"Пропущено: {report.skipped}\n"
                f"Ошибок: {report.errors}\n"
                f"Примерно освобождено: {format_size_bytes(report.freed_bytes)}\n\n"
                "Файлы можно восстановить из корзины Windows. "
                "Запись добавлена в «Корзина и журнал»."
            ),
        )
        self.statusBar().showMessage(
            f"Корзина: перемещено {report.moved}, пропущено {report.skipped}, ошибок {report.errors}."
        )

    def _on_current_file(self, item: object) -> None:
        media = item if isinstance(item, MediaFile) else None
        self._schedule_preview(media)

    def _schedule_preview(self, media: MediaFile | None) -> None:
        self._pending_preview = media
        if media is None:
            self._preview_request_id += 1
            self._preview.clear()
            return
        self._preview_timer.start()

    def _load_preview(self) -> None:
        self._preview_request_id += 1
        request_id = self._preview_request_id
        media = self._pending_preview
        worker = PreviewWorker(media, request_id, self._metadata, self._preview_signals)
        self._pool.start(worker)

    def _on_preview_ready(self, payload: object) -> None:
        if not isinstance(payload, MediaPreview):
            return
        if payload.request_id != self._preview_request_id:
            return
        self._preview.show_preview(payload)

    def _open_folder(self, item: object) -> None:
        if not isinstance(item, MediaFile):
            return
        folder = item.parent_folder
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _keep_preview_visible(self, _pos: int = 0, _index: int = 0) -> None:
        sizes = self._splitter.sizes()
        if len(sizes) != 2:
            return
        total = sizes[0] + sizes[1]
        min_table = 420
        min_preview = 260
        max_preview = min(560, max(min_preview, total - min_table))
        table, preview = sizes
        if preview < min_preview:
            preview = min_preview
        if preview > max_preview:
            preview = max_preview
        table = total - preview
        if table < min_table:
            table = min_table
            preview = total - table
        if (table, preview) != (sizes[0], sizes[1]):
            self._splitter.blockSignals(True)
            self._splitter.setSizes([table, preview])
            self._splitter.blockSignals(False)

    def _open_journal_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir())))

    def _clear_journal(self) -> None:
        if not ask_yes_no(
            self,
            "Очистить журнал",
            "Очистить пользовательскую историю операций? Технический файл app.log останется.",
        ):
            return
        self._journal.clear()
        self._journal_page.reload()
        self.statusBar().showMessage("История операций очищена.")

    def _export_report(self) -> None:
        files = list(self._model.files())
        if not files:
            show_info(
                self,
                "Нет данных",
                "Сначала выполните сканирование. Экспортируется список найденных файлов.",
            )
            return
        try:
            csv_path, json_path = self._reports.export_scan(files)
        except OSError as exc:
            show_warning(self, "Экспорт", f"Не удалось сохранить отчёт: {exc}")
            return
        self._journal.append(
            "report_export",
            "Экспортирован отчёт",
            {"csv": str(csv_path), "json": str(json_path), "files": len(files)},
        )
        self._journal_page.reload()
        show_info(
            self,
            "Отчёт сохранён",
            f"CSV:\n{csv_path}\n\nJSON:\n{json_path}",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(reports_dir())))

    def _log_recycle(self, report: RecycleReport) -> None:
        skipped_reasons = [
            {"name": item.name, "reason": item.reason}
            for item in report.items
            if item.skipped or item.error
        ][:40]
        moved_names = [item.name for item in report.items if item.moved][:40]
        self._journal.append(
            "recycle",
            (
                f"Корзина: перемещено {report.moved}, "
                f"пропущено {report.skipped}, ошибок {report.errors}"
            ),
            {
                "moved": report.moved,
                "skipped": report.skipped,
                "errors": report.errors,
                "freed_bytes": report.freed_bytes,
                "moved_names": moved_names,
                "skipped_or_failed": skipped_reasons,
            },
        )
        self._journal_page.reload()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._startup_placed:
            return
        self._startup_placed = True
        if self.isMaximized() or self.isFullScreen():
            self.showNormal()
        self._place_startup_window()

    def _place_startup_window(self) -> None:
        """Обычное окно по центру, с полями под панель задач — и фиксированную, и плавающую."""
        screen = self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
            return
        geo = screen.geometry()
        margin_x = max(
            WINDOW_EDGE_MARGIN_MIN,
            int(geo.width() * (1.0 - WINDOW_WIDTH_RATIO) / 2),
        )
        margin_y = max(
            WINDOW_EDGE_MARGIN_MIN,
            int(geo.height() * (1.0 - WINDOW_HEIGHT_RATIO) / 2),
        )
        bottom = max(WINDOW_BOTTOM_MARGIN_MIN, margin_y)
        max_w = max(640, geo.width() - 2 * margin_x)
        max_h = max(480, geo.height() - margin_y - bottom)
        width = min(WINDOW_DEFAULT_WIDTH, max_w)
        height = min(WINDOW_DEFAULT_HEIGHT, max_h)
        x = geo.x() + (geo.width() - width) // 2
        y = geo.y() + margin_y + max(0, (geo.height() - margin_y - bottom - height) // 2)
        self.setWindowState(Qt.WindowNoState)
        self.setMinimumSize(min(WINDOW_MIN_WIDTH, max_w), min(WINDOW_MIN_HEIGHT, max_h))
        self.setGeometry(QRect(x, y, width, height))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None:
            self._worker.cancel()
        super().closeEvent(event)
