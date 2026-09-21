"""Общие помощники тестов. Только временные каталоги pytest, без корзины Windows."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.host import volume_id
from models.media_file import MediaFile


def write_jpeg(path: Path, payload: bytes = b"\xff\xd8\xff\xdbfakejpeg") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def media_from_path(path: Path, scan_root: Path, *, selected: bool = False) -> MediaFile:
    st = path.stat()
    return MediaFile(
        path=path,
        name=path.name,
        extension=path.suffix,
        category="image",
        size_bytes=st.st_size,
        created_at=datetime.fromtimestamp(st.st_ctime),
        modified_at=datetime.fromtimestamp(st.st_mtime),
        drive=volume_id(path),
        parent_folder=path.parent,
        is_selected=selected,
        scan_root=scan_root,
        safety_status="safe",
        safety_reason="ok",
        scanned_size_bytes=st.st_size,
        scanned_modified_timestamp=st.st_mtime,
        normalized_path=path,
        mtime_ns=st.st_mtime_ns,
    )
