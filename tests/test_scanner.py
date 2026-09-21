"""Тесты сканера. Только tmp_path, без обхода реальных C: и D:."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import pytest

from core.scanner import ScanOptions, Scanner
from tests.conftest import write_jpeg


def test_finds_jpeg_skips_exe_and_txt(tmp_path: Path) -> None:
    write_jpeg(tmp_path / "ok.jpg")
    write_jpeg(tmp_path / "nested" / "shot.PNG")
    (tmp_path / "payload.exe").write_bytes(b"MZ")
    (tmp_path / "notes.txt").write_text("no", encoding="utf-8")
    result = Scanner().scan([tmp_path], options=ScanOptions())
    names = {item.name.casefold() for item in result.files}
    assert "ok.jpg" in names
    assert "shot.png" in names
    assert "payload.exe" not in names
    assert "notes.txt" not in names
    assert all(not item.is_selected for item in result.files)


def test_inaccessible_folder_does_not_stop_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_jpeg(tmp_path / "visible.jpg")
    locked = tmp_path / "locked"
    locked.mkdir()
    write_jpeg(locked / "hidden.jpg")
    import core.scanner as scanner_mod

    real_scandir = scanner_mod.os.scandir

    def fake_scandir(path: str | os.PathLike[str]):
        if Path(path) == locked:
            raise PermissionError("denied")
        return real_scandir(path)

    monkeypatch.setattr(scanner_mod.os, "scandir", fake_scandir)
    result = Scanner().scan([tmp_path], options=ScanOptions())
    names = {item.name.casefold() for item in result.files}
    assert "visible.jpg" in names
    assert "hidden.jpg" not in names
    assert result.summary.access_errors >= 1


def test_cancel_scan(tmp_path: Path) -> None:
    write_jpeg(tmp_path / "ok.jpg")
    cancel = threading.Event()
    cancel.set()
    result = Scanner().scan([tmp_path], options=ScanOptions(), cancel_event=cancel)
    assert result.summary.cancelled
    assert result.summary.files_found == 0


def test_duplicate_path_not_added_twice(tmp_path: Path) -> None:
    nested = tmp_path / "album"
    photo = write_jpeg(nested / "dup.jpg")
    result = Scanner().scan([tmp_path, nested], options=ScanOptions())
    matches = [item for item in result.files if item.name.casefold() == photo.name.casefold()]
    assert len(matches) == 1


def test_junction_is_not_followed(tmp_path: Path) -> None:
    scan_root = tmp_path / "scan"
    outside = tmp_path / "outside"
    write_jpeg(outside / "inside.jpg")
    scan_root.mkdir()
    visible = write_jpeg(scan_root / "root.jpg")
    link_dir = scan_root / "junction"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link_dir), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not link_dir.exists():
        pytest.skip(f"не удалось создать junction: {completed.stderr}")
    result = Scanner().scan([scan_root], options=ScanOptions())
    names = {item.name.casefold() for item in result.files}
    assert visible.name.casefold() in names
    assert "inside.jpg" not in names
