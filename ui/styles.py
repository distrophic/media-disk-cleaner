"""Светлая и тёмная темы интерфейса."""

from __future__ import annotations

from app.paths import resource_root


def _checkbox_qss(*, text: str, border: str, fill: str, checked: str) -> str:
    icon = (resource_root() / "icons" / "checkbox-checked.svg").resolve().as_posix()
    return f"""
QCheckBox {{
    color: {text};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    border-radius: 4px;
    background-color: {fill};
}}
QCheckBox::indicator:unchecked {{
    background-color: {fill};
    border: 1px solid {border};
    image: none;
}}
QCheckBox::indicator:checked {{
    background-color: {checked};
    border: 1px solid {checked};
    image: url("{icon}");
}}
"""


LIGHT_QSS = """
QMainWindow, QWidget#centralRoot {
    background: #f4f6fa;
    color: #111827;
    font-size: 13px;
}
QLabel {
    color: #111827;
    background: transparent;
}
QWidget#sidebar {
    background: #e8edf5;
    color: #111827;
    border-right: 1px solid #c5cedd;
}
QListWidget#navList {
    background: transparent;
    border: none;
    outline: none;
    padding: 8px;
    color: #111827;
}
QListWidget#navList::item {
    padding: 10px 12px;
    border-radius: 8px;
    margin: 2px 0;
    color: #111827;
}
QListWidget#navList::item:selected {
    background: #2f6fed;
    color: #ffffff;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #c5cedd;
    border-radius: 12px;
}
QLabel#cardTitle {
    color: #374151;
    font-size: 12px;
}
QLabel#cardValue {
    font-size: 18px;
    font-weight: 600;
    color: #0f172a;
}
QLineEdit, QComboBox, QListWidget#folderList, QPlainTextEdit {
    background: #ffffff;
    color: #111827;
    border: 1px solid #9aa6bc;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 28px;
}
QLineEdit:disabled, QComboBox:disabled {
    background: #eef2f6;
    color: #4b5563;
    border: 1px solid #c5cedd;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #111827;
    selection-background-color: #dce8ff;
    selection-color: #0f172a;
}
QPushButton {
    background: #2f6fed;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #245dd1;
}
QPushButton:disabled {
    background: #9aa6bc;
    color: #ffffff;
}
QPushButton#secondaryButton {
    background: #eef2f8;
    color: #111827;
    border: 1px solid #9aa6bc;
}
QPushButton#dangerButton {
    background: #c2410c;
    color: #ffffff;
}
QTableView {
    background: #ffffff;
    color: #111827;
    border: 1px solid #c5cedd;
    border-radius: 10px;
    gridline-color: #e6ebf3;
    selection-background-color: #dce8ff;
    selection-color: #0f172a;
    alternate-background-color: #f7f9fc;
}
QHeaderView::section {
    background: #eef2f8;
    color: #111827;
    border: none;
    border-right: 1px solid #c5cedd;
    padding: 8px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #9aa6bc;
    border-radius: 8px;
    background: #ffffff;
    color: #111827;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    background: #2f6fed;
    border-radius: 7px;
}
QStatusBar, QStatusBar QLabel {
    background: #e8edf5;
    color: #111827;
}
QWidget#previewPane {
    background: #eef2f8;
    border: 1px solid #c5cedd;
    border-radius: 12px;
}
QFrame#previewFrame {
    background: #ffffff;
    border: 1px solid #c5cedd;
    border-radius: 10px;
}
QLabel#previewTitle {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
}
QLabel#previewCaption {
    color: #4b5563;
    font-size: 11px;
}
QLabel#previewValue {
    color: #111827;
}
QLabel#previewMessage {
    color: #374151;
}
QLabel#previewImage {
    color: #111827;
}
QSplitter::handle:horizontal {
    background: #c5cedd;
    width: 3px;
    margin: 12px 2px;
    border-radius: 2px;
}
QScrollArea#previewScroll,
QWidget#previewScrollViewport,
QWidget#previewFields {
    background: #eef2f8;
    color: #111827;
    border: none;
}
QScrollArea#previewScroll QScrollBar:vertical {
    background: #e8edf5;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollArea#previewScroll QScrollBar::handle:vertical {
    background: #c5cedd;
    min-height: 24px;
    border-radius: 4px;
}
QScrollArea#previewScroll QScrollBar::add-line:vertical,
QScrollArea#previewScroll QScrollBar::sub-line:vertical {
    height: 0;
}
"""

DARK_QSS = """
QMainWindow, QWidget#centralRoot {
    background: #121722;
    color: #e8eefc;
    font-size: 13px;
}
QWidget#sidebar {
    background: #0f141e;
    border-right: 1px solid #2a3346;
}
QListWidget#navList {
    background: transparent;
    border: none;
    outline: none;
    padding: 8px;
}
QListWidget#navList::item {
    padding: 10px 12px;
    border-radius: 8px;
    margin: 2px 0;
}
QListWidget#navList::item:selected {
    background: #3b82f6;
    color: #ffffff;
}
QFrame#card {
    background: #1a2230;
    border: 1px solid #2a3346;
    border-radius: 12px;
}
QLabel#cardTitle {
    color: #9aa7c2;
    font-size: 12px;
}
QLabel#cardValue {
    font-size: 18px;
    font-weight: 600;
    color: #f3f7ff;
}
QLineEdit, QComboBox, QListWidget#folderList, QPlainTextEdit {
    background: #151c28;
    border: 1px solid #2a3346;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 28px;
    color: #e8eefc;
}
QPushButton {
    background: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #2563eb;
}
QPushButton:disabled {
    background: #2a3346;
    color: #7b879c;
}
QPushButton#secondaryButton {
    background: #1a2230;
    color: #d5def0;
    border: 1px solid #2a3346;
}
QPushButton#dangerButton {
    background: #b45309;
    color: #ffffff;
}
QTableView {
    background: #151c28;
    border: 1px solid #2a3346;
    border-radius: 10px;
    gridline-color: #2a3346;
    selection-background-color: #1e3a8a;
    selection-color: #f8fbff;
    alternate-background-color: #121926;
    color: #e8eefc;
}
QHeaderView::section {
    background: #1a2230;
    color: #d5def0;
    border: none;
    border-right: 1px solid #2a3346;
    padding: 8px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #2a3346;
    border-radius: 8px;
    background: #151c28;
    text-align: center;
    color: #e8eefc;
    min-height: 18px;
}
QProgressBar::chunk {
    background: #3b82f6;
    border-radius: 7px;
}
QStatusBar {
    background: #0f141e;
    color: #9aa7c2;
}
QLabel {
    color: #e8eefc;
    background: transparent;
}
QWidget#previewPane {
    background: #151c28;
    border: 1px solid #2a3346;
    border-radius: 12px;
}
QFrame#previewFrame {
    background: #1a2230;
    border: 1px solid #2a3346;
    border-radius: 10px;
}
QLabel#previewTitle {
    font-size: 15px;
    font-weight: 600;
    color: #f3f7ff;
}
QLabel#previewCaption {
    color: #9aa7c2;
    font-size: 11px;
}
QLabel#previewValue, QLabel#previewMessage, QLabel#previewImage {
    color: #e8eefc;
}
QSplitter::handle:horizontal {
    background: #2a3346;
    width: 3px;
    margin: 12px 2px;
    border-radius: 2px;
}
QScrollArea#previewScroll,
QWidget#previewScrollViewport,
QWidget#previewFields {
    background: #151c28;
    color: #e8eefc;
    border: none;
}
QScrollArea#previewScroll QScrollBar:vertical {
    background: #121722;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollArea#previewScroll QScrollBar::handle:vertical {
    background: #2a3346;
    min-height: 24px;
    border-radius: 4px;
}
QScrollArea#previewScroll QScrollBar::add-line:vertical,
QScrollArea#previewScroll QScrollBar::sub-line:vertical {
    height: 0;
}
"""


def theme_qss(dark: bool) -> str:
    if dark:
        return DARK_QSS + _checkbox_qss(
            text="#e8eefc",
            border="#4b5870",
            fill="#151c28",
            checked="#3b82f6",
        )
    return LIGHT_QSS + _checkbox_qss(
        text="#111827",
        border="#9aa6bc",
        fill="#ffffff",
        checked="#2f6fed",
    )
