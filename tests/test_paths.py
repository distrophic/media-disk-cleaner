"""Пути ресурсов и пользовательских данных — не в каталог сборки."""

from __future__ import annotations

import os
from pathlib import Path

from app.paths import resource_root, user_data_root


def test_user_data_is_localappdata(monkeypatch) -> None:
    fake = Path("C:/Users/tester/AppData/Local")
    monkeypatch.setenv("LOCALAPPDATA", str(fake))
    root = user_data_root()
    assert root == fake / "MediaDiskCleaner"
    assert "MEIPASS" not in str(root).upper()


def test_resource_root_from_source() -> None:
    root = resource_root()
    assert (root / "main.py").is_file()
    meipass = os.environ.get("_MEIPASS", "")
    if meipass:
        assert root != Path(meipass)
