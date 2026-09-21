"""Безопасные сведения о томах C: и D:.

Модуль только читает. Не сканирует содержимое, не меняет буквы дисков
и не запрашивает права администратора.
"""

from __future__ import annotations

import ctypes
import shutil
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from core.safety_validator import normalize_windows_path

_DRIVE_TYPE_NAMES = {
    0: "unknown",
    1: "no_root",
    2: "removable",
    3: "fixed",
    4: "remote",
    5: "optical",
    6: "ramdisk",
}

_DRIVE_TYPE_LABELS_RU = {
    "unknown": "неизвестно",
    "no_root": "нет корневого каталога",
    "removable": "съёмный",
    "fixed": "фиксированный",
    "remote": "сетевой",
    "optical": "оптический",
    "ramdisk": "RAM-диск",
}


@dataclass(frozen=True, slots=True)
class DriveInfo:
    letter: str
    root_path: Path
    available: bool
    label: str
    total_bytes: int | None
    used_bytes: int | None
    free_bytes: int | None
    drive_type: str
    type_label_ru: str
    status_note: str


class DriveService:
    """Опрос томов C: и D: без обхода пользовательских файлов."""

    TARGET_LETTERS = ("C", "D")

    def list_target_drives(self) -> list[DriveInfo]:
        return [self.inspect_letter(letter) for letter in self.TARGET_LETTERS]

    def inspect_letter(self, letter: str) -> DriveInfo:
        clean = letter.strip().rstrip(":\\/").upper()[:1] or "?"
        root = Path(f"{clean}:/")
        normalized = normalize_windows_path(root)
        root_path = normalized if normalized is not None else root
        if not self._root_exists(root_path):
            return DriveInfo(
                letter=f"{clean}:",
                root_path=root_path,
                available=False,
                label="",
                total_bytes=None,
                used_bytes=None,
                free_bytes=None,
                drive_type="no_root",
                type_label_ru=_DRIVE_TYPE_LABELS_RU["no_root"],
                status_note="диск недоступен",
            )
        drive_type = self._drive_type(root_path)
        label = self._volume_label(root_path)
        total, used, free = self._usage(root_path)
        return DriveInfo(
            letter=f"{clean}:",
            root_path=root_path,
            available=True,
            label=label,
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            drive_type=drive_type,
            type_label_ru=_DRIVE_TYPE_LABELS_RU.get(drive_type, drive_type),
            status_note="",
        )

    def _root_exists(self, root: Path) -> bool:
        try:
            return root.exists()
        except OSError:
            return False

    def _usage(self, root: Path) -> tuple[int | None, int | None, int | None]:
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            return (None, None, None)
        return (int(usage.total), int(usage.used), int(usage.free))

    def _drive_type(self, root: Path) -> str:
        try:
            get_type = ctypes.windll.kernel32.GetDriveTypeW
            get_type.argtypes = [wintypes.LPCWSTR]
            get_type.restype = wintypes.UINT
            code = int(get_type(str(root)))
        except (AttributeError, OSError, ValueError):
            return "unknown"
        return _DRIVE_TYPE_NAMES.get(code, "unknown")

    def _volume_label(self, root: Path) -> str:
        try:
            get_info = ctypes.windll.kernel32.GetVolumeInformationW
            volume_name = ctypes.create_unicode_buffer(261)
            fs_name = ctypes.create_unicode_buffer(261)
            serial = wintypes.DWORD()
            max_component = wintypes.DWORD()
            flags = wintypes.DWORD()
            get_info.argtypes = [
                wintypes.LPCWSTR,
                wintypes.LPWSTR,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPWSTR,
                wintypes.DWORD,
            ]
            get_info.restype = wintypes.BOOL
            ok = get_info(
                str(root),
                volume_name,
                261,
                ctypes.byref(serial),
                ctypes.byref(max_component),
                ctypes.byref(flags),
                fs_name,
                261,
            )
        except (AttributeError, OSError, ValueError):
            return ""
        if not ok:
            return ""
        return str(volume_name.value or "")
