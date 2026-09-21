"""Сведения о томах: C:/D: на Windows, домашние и съёмные точки на Linux.

Модуль только читает. Не сканирует содержимое и не запрашивает root/UAC.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.host import is_windows, volume_id
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

_SKIP_FS = frozenset(
    {
        "autofs",
        "bpf",
        "cgroup",
        "cgroup2",
        "debugfs",
        "devpts",
        "devtmpfs",
        "efivarfs",
        "fusectl",
        "fuse.gvfsd-fuse",
        "nsfs",
        "overlay",
        "proc",
        "pstore",
        "securityfs",
        "squashfs",
        "sysfs",
        "tmpfs",
        "tracefs",
    }
)


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
    """Опрос томов без обхода пользовательских файлов."""

    TARGET_LETTERS = ("C", "D")

    def list_target_drives(self) -> list[DriveInfo]:
        if is_windows():
            return [self.inspect_letter(letter) for letter in self.TARGET_LETTERS]
        return self._list_posix_volumes()

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
        drive_type = self._windows_drive_type(root_path)
        label = self._windows_volume_label(root_path)
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

    def _list_posix_volumes(self) -> list[DriveInfo]:
        found: list[DriveInfo] = []
        seen: set[str] = set()
        home = Path.home()
        found.append(self._posix_info(home, label="домашний каталог", drive_type="fixed"))
        seen.add(str(home))
        for mount in self._posix_mount_points():
            key = str(mount)
            if key in seen:
                continue
            seen.add(key)
            kind = "removable" if _looks_removable(mount) else "fixed"
            found.append(self._posix_info(mount, label=mount.name or str(mount), drive_type=kind))
        return found

    def _posix_info(self, root: Path, *, label: str, drive_type: str) -> DriveInfo:
        normalized = normalize_windows_path(root) or root
        available = self._root_exists(normalized)
        total = used = free = None
        if available:
            total, used, free = self._usage(normalized)
        letter = volume_id(normalized)
        return DriveInfo(
            letter=letter,
            root_path=normalized,
            available=available,
            label=label,
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            drive_type=drive_type,
            type_label_ru=_DRIVE_TYPE_LABELS_RU.get(drive_type, drive_type),
            status_note="" if available else "том недоступен",
        )

    def _posix_mount_points(self) -> list[Path]:
        mounts_file = Path("/proc/mounts")
        if not mounts_file.is_file():
            return []
        prefixes = ("/home", "/media", "/mnt", "/run/media", "/data")
        result: list[Path] = []
        try:
            lines = mounts_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue
            raw_mount, fs_type = parts[1], parts[2]
            mount = Path(_unescape_mount(raw_mount))
            if fs_type in _SKIP_FS:
                continue
            text = str(mount)
            if text == "/":
                continue
            if not text.startswith(prefixes):
                continue
            if text in {"/home", "/media", "/mnt", "/run", "/run/media"}:
                continue
            result.append(mount)
        return result

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

    def _windows_drive_type(self, root: Path) -> str:
        if not is_windows():
            return "unknown"
        try:
            import ctypes
            from ctypes import wintypes

            get_type = ctypes.windll.kernel32.GetDriveTypeW
            get_type.argtypes = [wintypes.LPCWSTR]
            get_type.restype = wintypes.UINT
            code = int(get_type(str(root)))
        except (AttributeError, OSError, ValueError):
            return "unknown"
        return _DRIVE_TYPE_NAMES.get(code, "unknown")

    def _windows_volume_label(self, root: Path) -> str:
        if not is_windows():
            return ""
        try:
            import ctypes
            from ctypes import wintypes

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


def _unescape_mount(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t")


def _looks_removable(path: Path) -> bool:
    text = str(path)
    return text.startswith("/media/") or text.startswith("/run/media/") or text.startswith("/mnt/")
