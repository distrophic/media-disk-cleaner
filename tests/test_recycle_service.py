"""Тесты RecycleService. Всегда mock send2trash, никогда настоящая корзина."""

from __future__ import annotations

import ast
from pathlib import Path

from core.recycle_service import RecycleService
from models.safety_result import VerifiedMediaTarget
from tests.conftest import media_from_path, write_jpeg

_RECYCLE_SOURCE = Path(__file__).resolve().parents[1] / "core" / "recycle_service.py"


def _service(trash_fn) -> RecycleService:
    return RecycleService(trash_fn=trash_fn)


def test_unselected_file_not_recycled(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    calls: list[str] = []
    report = _service(calls.append).recycle_selected(
        [media_from_path(photo, tmp_path, selected=False)]
    )
    assert report.moved == 0
    assert report.skipped == 1
    assert calls == []
    assert photo.exists()


def test_missing_file_skipped(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=True)
    photo.unlink()
    calls: list[str] = []
    report = _service(calls.append).recycle_selected([media])
    assert report.moved == 0
    assert report.skipped == 1
    assert calls == []


def test_changed_file_skipped(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=True)
    photo.write_bytes(photo.read_bytes() + b"extra")
    calls: list[str] = []
    report = _service(calls.append).recycle_selected([media])
    assert report.moved == 0
    assert report.skipped == 1
    assert calls == []
    assert photo.exists()


def test_recheck_before_send2trash(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=True)
    calls: list[str] = []
    report = _service(calls.append).recycle_selected([media])
    assert report.moved == 1
    assert len(calls) == 1
    assert photo.exists()


def test_error_on_one_file_does_not_stop_others(tmp_path: Path) -> None:
    first = write_jpeg(tmp_path / "a.jpg")
    second = write_jpeg(tmp_path / "b.jpg")
    calls: list[str] = []

    def boom(path: str) -> None:
        calls.append(path)
        raise OSError("simulated send2trash failure")

    report = RecycleService(trash_fn=boom).recycle_selected(
        [
            media_from_path(first, tmp_path, selected=True),
            media_from_path(second, tmp_path, selected=True),
        ]
    )
    assert report.errors == 2
    assert report.moved == 0
    assert len(calls) == 2
    assert first.exists() and second.exists()


def test_does_not_call_remove_unlink_or_rmtree() -> None:
    tree = ast.parse(_RECYCLE_SOURCE.read_text(encoding="utf-8"))
    banned: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name in {"remove", "unlink", "rmtree", "system"}:
            banned.append(name)
    assert banned == []


def test_recycle_verified_rejects_plain_path_contract(tmp_path: Path) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=True)
    calls: list[str] = []
    service = _service(calls.append)
    target = VerifiedMediaTarget(
        normalized_path=media.normalized_path,
        category="image",
        size_bytes=media.size_bytes,
        modified_timestamp=media.scanned_modified_timestamp,
        mtime_ns=media.mtime_ns,
        scan_root=tmp_path,
        extension=media.extension,
        explicitly_selected=True,
    )
    item = service.recycle_verified(target)
    assert item.moved
    assert calls
    assert photo.exists()
