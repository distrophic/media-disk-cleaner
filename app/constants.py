"""Неизменяемые константы приложения.

Системные исключения и список опасных расширений нельзя ослабить через настройки.
Список медиарасширений живёт в ``core.file_classifier`` и может расширяться
только совместимыми типами изображений, видео и аудио.
"""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "Media Disk Cleaner"
APP_ID: Final[str] = "MediaDiskCleaner"
APP_VERSION: Final[str] = "0.1.0"

# Стартовое окно: обычное, не на весь экран. Поля оставляют место
# и обычной панели задач, и плавающей/автоскрываемой.
WINDOW_DEFAULT_WIDTH: Final[int] = 1280
WINDOW_DEFAULT_HEIGHT: Final[int] = 800
WINDOW_MIN_WIDTH: Final[int] = 960
WINDOW_MIN_HEIGHT: Final[int] = 600
WINDOW_EDGE_MARGIN_MIN: Final[int] = 48
WINDOW_BOTTOM_MARGIN_MIN: Final[int] = 80
WINDOW_WIDTH_RATIO: Final[float] = 0.86
WINDOW_HEIGHT_RATIO: Final[float] = 0.82

CATEGORY_IMAGE: Final[str] = "image"
CATEGORY_VIDEO: Final[str] = "video"
CATEGORY_AUDIO: Final[str] = "audio"

MEDIA_CATEGORIES: Final[frozenset[str]] = frozenset(
    {CATEGORY_IMAGE, CATEGORY_VIDEO, CATEGORY_AUDIO}
)

SAFETY_STATUS_SAFE: Final[str] = "safe"
SAFETY_STATUS_UNSAFE: Final[str] = "unsafe"

PURPOSE_INDEX: Final[str] = "index"
PURPOSE_RECYCLE: Final[str] = "recycle"
PURPOSE_PREVIEW: Final[str] = "preview"

PREVIEW_THUMB_MAX_PX: Final[int] = 320
PREVIEW_MAX_IMAGE_BYTES: Final[int] = 40 * 1024 * 1024
PREVIEW_MAX_PIXELS: Final[int] = 40_000_000

SCAN_MODE_QUICK: Final[str] = "quick"
SCAN_MODE_SELECTIVE: Final[str] = "selective"
SCAN_MODE_EXTENDED: Final[str] = "extended"

SCAN_BATCH_SIZE: Final[int] = 200
SCAN_MAX_DEPTH: Final[int] = 128
SCAN_MAX_SKIPPED_REASONS: Final[int] = 1000

LARGE_FILE_THRESHOLD_BYTES: Final[int] = 100 * 1024 * 1024
OLD_FILE_AGE_DAYS: Final[int] = 365

QUICK_SCAN_FOLDER_NAMES: Final[tuple[str, ...]] = (
    "Pictures",
    "Videos",
    "Music",
    "Downloads",
    "Desktop",
    "Documents",
)

# Атрибуты Windows (winnt.h). Используются только для чтения.
FILE_ATTRIBUTE_READONLY: Final[int] = 0x1
FILE_ATTRIBUTE_HIDDEN: Final[int] = 0x2
FILE_ATTRIBUTE_SYSTEM: Final[int] = 0x4
FILE_ATTRIBUTE_DIRECTORY: Final[int] = 0x10
FILE_ATTRIBUTE_REPARSE_POINT: Final[int] = 0x400

# Имена каталогов у корня любого тома (C:\, D:\ и т.д.).
EXCLUDED_DRIVE_ROOT_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        "windows",
        "windows.old",
        "program files",
        "program files (x86)",
        "programdata",
        "recovery",
        "system volume information",
        "$recycle.bin",
        "perflogs",
        "boot",
        "efi",
        "msocache",
        "config.msi",
        "documents and settings",
    }
)

# Первый компонент POSIX-пути: /usr, /etc, /proc и т.д.
EXCLUDED_POSIX_ROOT_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        "bin",
        "boot",
        "dev",
        "etc",
        "lib",
        "lib32",
        "lib64",
        "libx32",
        "lost+found",
        "opt",
        "proc",
        "root",
        "run",
        "sbin",
        "snap",
        "srv",
        "sys",
        "tmp",
        "usr",
        "var",
    }
)

# Имена, которые нельзя обходить даже во вложенных каталогах.
EXCLUDED_DIR_NAMES_ANYWHERE: Final[frozenset[str]] = frozenset(
    {
        "windowsapps",
        "$recycle.bin",
        "system volume information",
        "config.msi",
        "msocache",
        "windows.old",
        "lost+found",
        ".trash",
        ".trash-1000",
    }
)

# Служебные каталоги антивирусов и защиты Windows (имя компонента пути).
EXCLUDED_SECURITY_PRODUCT_DIR_NAMES: Final[frozenset[str]] = frozenset(
    {
        "windows defender",
        "windowsdefender",
        "microsoft defender",
        "wdav",
        "avast software",
        "avg",
        "avg antivirus",
        "kaspersky lab",
        "kaspersky",
        "norton",
        "norton security",
        "mcafee",
        "eset",
        "bitdefender",
        "malwarebytes",
        "sophos",
        "drweb",
        "dr.web",
        "avp",
        "kaspersky antivirus",
    }
)

PROTECTED_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "pagefile.sys",
        "hiberfil.sys",
        "swapfile.sys",
        "bootmgr",
        "bootnxt",
        "bootstat.dat",
        "ntldr",
        "ntdetect.com",
        "ntuser.dat",
        "ntuser.dat.log",
        "ntuser.dat.log1",
        "ntuser.dat.log2",
        "usrclass.dat",
        "sam",
        "security",
        "software",
        "system",
        "default",
        "system.dat",
        "user.dat",
    }
)

# Расширения, которые нельзя считать медиафайлами даже через настройки.
DANGEROUS_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".exe",
        ".dll",
        ".sys",
        ".drv",
        ".ocx",
        ".efi",
        ".scr",
        ".com",
        ".bat",
        ".cmd",
        ".ps1",
        ".psm1",
        ".psd1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".wsf",
        ".wsh",
        ".msi",
        ".msp",
        ".mst",
        ".reg",
        ".inf",
        ".lnk",
        ".url",
        ".pif",
        ".cpl",
        ".msc",
        ".cab",
        ".appx",
        ".appxbundle",
        ".msix",
        ".msixbundle",
        ".so",
        ".dylib",
    }
)

REASON_NOT_ABSOLUTE: Final[str] = "path_not_absolute"
REASON_INVALID_PATH: Final[str] = "invalid_path"
REASON_MISSING: Final[str] = "file_missing"
REASON_NOT_A_FILE: Final[str] = "not_a_regular_file"
REASON_SYMLINK: Final[str] = "symbolic_link"
REASON_JUNCTION: Final[str] = "junction_or_reparse_point"
REASON_SYSTEM_PATH: Final[str] = "system_excluded_path"
REASON_SYSTEM_ATTRIBUTE: Final[str] = "system_attribute"
REASON_PROTECTED_NAME: Final[str] = "protected_file_name"
REASON_UNKNOWN_EXTENSION: Final[str] = "unknown_or_disallowed_extension"
REASON_DANGEROUS_EXTENSION: Final[str] = "dangerous_extension"
REASON_OUTSIDE_SCAN_ROOT: Final[str] = "outside_scan_roots"
REASON_RESOLVED_ESCAPE: Final[str] = "resolved_path_escapes_scan_roots"
REASON_PARENT_REPARSE: Final[str] = "parent_reparse_point"
REASON_METADATA_UNAVAILABLE: Final[str] = "metadata_unavailable"
REASON_FILE_CHANGED: Final[str] = "file_changed_after_scan"
REASON_PATH_CHANGED: Final[str] = "path_changed_after_scan"
REASON_CATEGORY_MISMATCH: Final[str] = "category_mismatch"
REASON_NOT_SELECTED: Final[str] = "not_explicitly_selected"
REASON_ACCESS: Final[str] = "access_denied_or_os_error"
REASON_EMPTY_SCAN_ROOTS: Final[str] = "empty_scan_roots"
REASON_MISSING_SCAN_SNAPSHOT: Final[str] = "missing_scan_snapshot"
REASON_OK: Final[str] = "ok"
