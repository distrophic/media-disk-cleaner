"""Тесты SafetyValidator. Не удаляют файлы и не ходят в пользовательские C:/D:."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.constants import PURPOSE_INDEX, PURPOSE_RECYCLE
from core.file_classifier import FileClassifier
from core.safety_validator import SafetyValidator, is_excluded_system_path
from tests.conftest import media_from_path, write_jpeg


@pytest.fixture
def validator() -> SafetyValidator:
    return SafetyValidator()


def test_ordinary_image_is_safe_for_index(tmp_path: Path, validator: SafetyValidator) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    result = validator.is_safe_media_file(photo, scan_roots=[tmp_path], purpose=PURPOSE_INDEX)
    assert result.safe
    assert result.category == "image"


def test_system_path_blocked(validator: SafetyValidator) -> None:
    windows = Path(r"C:\Windows\notepad.exe")
    result = validator.is_safe_media_file(
        windows,
        scan_roots=[Path(r"C:\Windows")],
        purpose=PURPOSE_INDEX,
    )
    assert not result.safe
    assert result.reason == "system_excluded_path"
    assert is_excluded_system_path(windows)


def test_symlink_blocked(tmp_path: Path, validator: SafetyValidator) -> None:
    target = write_jpeg(tmp_path / "real.jpg")
    link = tmp_path / "link.jpg"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("нет прав на создание symlink")
    result = validator.is_safe_media_file(link, scan_roots=[tmp_path], purpose=PURPOSE_INDEX)
    assert not result.safe
    assert result.reason in {"symbolic_link", "junction_or_reparse_point"}


def test_unknown_extension_blocked(tmp_path: Path, validator: SafetyValidator) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("hello", encoding="utf-8")
    result = validator.is_safe_media_file(text, scan_roots=[tmp_path], purpose=PURPOSE_INDEX)
    assert not result.safe
    assert result.reason == "unknown_or_disallowed_extension"


def test_directory_not_accepted_as_file(tmp_path: Path, validator: SafetyValidator) -> None:
    folder = tmp_path / "album.jpg"
    folder.mkdir()
    result = validator.is_safe_media_file(folder, scan_roots=[tmp_path], purpose=PURPOSE_INDEX)
    assert not result.safe


def test_file_outside_scan_root_blocked(tmp_path: Path, validator: SafetyValidator) -> None:
    inside = tmp_path / "in"
    outside = tmp_path / "out"
    inside.mkdir()
    outside.mkdir()
    leak = write_jpeg(outside / "leak.jpg")
    result = validator.is_safe_media_file(leak, scan_roots=[inside], purpose=PURPOSE_INDEX)
    assert not result.safe
    assert result.reason == "outside_scan_roots"


def test_missing_file_blocked(tmp_path: Path, validator: SafetyValidator) -> None:
    missing = tmp_path / "gone.jpg"
    result = validator.is_safe_media_file(missing, scan_roots=[tmp_path], purpose=PURPOSE_INDEX)
    assert not result.safe
    assert result.reason == "file_missing"


def test_unselected_cannot_recycle(tmp_path: Path, validator: SafetyValidator) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=False)
    result = validator.is_safe_media_file(
        photo,
        scan_roots=[tmp_path],
        explicitly_selected=False,
        expected_metadata=media.expected_metadata(),
        expected_category="image",
        expected_path=photo,
        purpose=PURPOSE_RECYCLE,
    )
    assert not result.safe
    assert result.reason == "not_explicitly_selected"


def test_changed_file_skipped(tmp_path: Path, validator: SafetyValidator) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    media = media_from_path(photo, tmp_path, selected=True)
    photo.write_bytes(photo.read_bytes() + b"\x00")
    result = validator.is_safe_media_file(
        photo,
        scan_roots=[tmp_path],
        explicitly_selected=True,
        expected_metadata=media.expected_metadata(),
        expected_category="image",
        expected_path=photo,
        purpose=PURPOSE_RECYCLE,
    )
    assert not result.safe
    assert result.reason == "file_changed_after_scan"


def test_replaced_with_symlink_skipped(tmp_path: Path, validator: SafetyValidator) -> None:
    photo = write_jpeg(tmp_path / "ok.jpg")
    other = write_jpeg(tmp_path / "other.jpg", b"\xff\xd8other")
    media = media_from_path(photo, tmp_path, selected=True)
    photo.unlink()
    try:
        os.symlink(other, photo)
    except OSError:
        pytest.skip("нет прав на создание symlink")
    result = validator.is_safe_media_file(
        photo,
        scan_roots=[tmp_path],
        explicitly_selected=True,
        expected_metadata=media.expected_metadata(),
        expected_category="image",
        expected_path=photo,
        purpose=PURPOSE_RECYCLE,
    )
    assert not result.safe
    assert result.reason in {"symbolic_link", "junction_or_reparse_point", "file_changed_after_scan"}


def test_system_exclusion_cannot_be_enabled_via_settings() -> None:
    classifier = FileClassifier(extra_extensions={".sys": "image"})
    assert classifier.classify("driver.sys") is None
    windows = Path(r"C:\Windows\System32")
    assert is_excluded_system_path(windows)
    opened = FileClassifier(extra_extensions={".exe": "image"})
    assert opened.classify(Path(r"C:\Windows\notepad.exe")) is None
