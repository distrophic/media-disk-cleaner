"""Системные диалоги обычного размера. В тёмной теме только белый текст."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

_DARK_TEXT_QSS = """
QMessageBox QLabel {
    color: #ffffff;
}
"""


def _is_dark(parent: QWidget | None) -> bool:
    return bool(parent is not None and getattr(parent, "_dark", False))


def _prepare(box: QMessageBox, parent: QWidget | None) -> None:
    if _is_dark(parent):
        box.setStyleSheet(_DARK_TEXT_QSS)
    else:
        box.setStyleSheet("")
    box.adjustSize()


def ask_yes_no(parent: QWidget | None, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    box.setDefaultButton(QMessageBox.No)
    yes = box.button(QMessageBox.Yes)
    no = box.button(QMessageBox.No)
    if yes is not None:
        yes.setText("Да")
    if no is not None:
        no.setText("Нет")
    _prepare(box, parent)
    return box.exec() == QMessageBox.Yes


def ask_ok_cancel(parent: QWidget | None, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    box.setDefaultButton(QMessageBox.Cancel)
    ok = box.button(QMessageBox.Ok)
    cancel = box.button(QMessageBox.Cancel)
    if ok is not None:
        ok.setText("Продолжить")
    if cancel is not None:
        cancel.setText("Отмена")
    _prepare(box, parent)
    return box.exec() == QMessageBox.Ok


def show_info(parent: QWidget | None, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Ok)
    ok = box.button(QMessageBox.Ok)
    if ok is not None:
        ok.setText("ОК")
    _prepare(box, parent)
    box.exec()


def show_warning(parent: QWidget | None, title: str, text: str) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.Ok)
    ok = box.button(QMessageBox.Ok)
    if ok is not None:
        ok.setText("ОК")
    _prepare(box, parent)
    box.exec()
