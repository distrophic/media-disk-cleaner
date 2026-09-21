"""Тесты классификатора расширений."""

from __future__ import annotations

from pathlib import Path

from core.file_classifier import FileClassifier


def test_ordinary_image_classified() -> None:
    classifier = FileClassifier()
    assert classifier.classify(Path("photo.jpg")) == "image"
    assert classifier.classify("vacation.png") == "image"


def test_extension_case_insensitive() -> None:
    classifier = FileClassifier()
    assert classifier.classify("PICTURE.JPG") == "image"
    assert classifier.classify("clip.Mp4") == "video"
    assert classifier.classify("track.MP3") == "audio"


def test_unknown_extension_not_media() -> None:
    classifier = FileClassifier()
    assert classifier.classify("notes.txt") is None
    assert classifier.classify("archive.zip") is None


def test_exe_not_media_even_via_settings() -> None:
    classifier = FileClassifier(extra_extensions={".exe": "image", ".dll": "audio"})
    assert classifier.classify("setup.exe") is None
    assert classifier.classify("ntdll.dll") is None
    assert ".exe" not in classifier.allowed_extensions()
