"""Идентификаторы томов и ключи фильтров."""

from __future__ import annotations

from pathlib import Path

from app.host import drive_key, folder_filter_key, folder_filter_match, is_windows, volume_id


def test_volume_id_for_windows_style_drive() -> None:
    if not is_windows():
        path = Path("/home/alice/Pictures/a.jpg")
        assert volume_id(path) == "/home"
        assert drive_key("/home") == "/home"
        return
    path = Path(r"D:\Photos\a.jpg")
    assert volume_id(path).upper().startswith("D")
    assert drive_key("d:\\") == "D:"


def test_folder_filter_prefix(tmp_path: Path) -> None:
    nested = tmp_path / "album" / "shot.jpg"
    needle = folder_filter_key(tmp_path / "album")
    hay = folder_filter_key(nested)
    assert folder_filter_match(hay, needle)
    assert not folder_filter_match(folder_filter_key(tmp_path / "other" / "x.jpg"), needle)
