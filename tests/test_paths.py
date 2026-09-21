"""Пути ресурсов и пользовательских данных — не в каталог сборки."""

from __future__ import annotations

import os
from pathlib import Path

from app.host import is_windows
from app.paths import resource_root, user_data_root


def test_user_data_is_outside_build(monkeypatch, tmp_path: Path) -> None:
    if is_windows():
        fake = tmp_path / "Local"
        monkeypatch.setenv("LOCALAPPDATA", str(fake))
    else:
        fake = tmp_path / "share"
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(fake))
    root = user_data_root()
    assert root == fake / "MediaDiskCleaner"
    assert "MEIPASS" not in str(root).upper()


def test_resource_root_from_source() -> None:
    root = resource_root()
    assert (root / "main.py").is_file()
    meipass = os.environ.get("_MEIPASS", "")
    if meipass:
        assert root != Path(meipass)
