"""Централизованная проверка безопасности медиафайлов.

Модуль не удаляет файлы, не меняет ACL и не запрашивает повышение прав.
Если состояние объекта нельзя надёжно определить, результат — unsafe.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Collection, Sequence
from pathlib import Path

from app.constants import (
    EXCLUDED_DIR_NAMES_ANYWHERE,
    EXCLUDED_DRIVE_ROOT_DIR_NAMES,
    EXCLUDED_POSIX_ROOT_DIR_NAMES,
    EXCLUDED_SECURITY_PRODUCT_DIR_NAMES,
    FILE_ATTRIBUTE_HIDDEN,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_ATTRIBUTE_SYSTEM,
    PURPOSE_INDEX,
    PURPOSE_RECYCLE,
    PROTECTED_FILE_NAMES,
    REASON_ACCESS,
    REASON_CATEGORY_MISMATCH,
    REASON_DANGEROUS_EXTENSION,
    REASON_EMPTY_SCAN_ROOTS,
    REASON_FILE_CHANGED,
    REASON_INVALID_PATH,
    REASON_JUNCTION,
    REASON_METADATA_UNAVAILABLE,
    REASON_MISSING,
    REASON_MISSING_SCAN_SNAPSHOT,
    REASON_NOT_A_FILE,
    REASON_NOT_ABSOLUTE,
    REASON_NOT_SELECTED,
    REASON_OK,
    REASON_OUTSIDE_SCAN_ROOT,
    REASON_PARENT_REPARSE,
    REASON_PATH_CHANGED,
    REASON_PROTECTED_NAME,
    REASON_RESOLVED_ESCAPE,
    REASON_SYMLINK,
    REASON_SYSTEM_ATTRIBUTE,
    REASON_SYSTEM_PATH,
    REASON_UNKNOWN_EXTENSION,
    SAFETY_STATUS_SAFE,
    SAFETY_STATUS_UNSAFE,
)
from core.file_classifier import FileClassifier, is_dangerous_extension, normalize_extension
from models.safety_result import ExpectedMetadata, SafetyResult

_DRIVE_ROOT_LENGTH = 2


def normalize_windows_path(path: Path | str) -> Path | None:
    """Абсолютный нормализованный путь без перехода по ссылкам.

    Не использует ``resolve()``: resolve следует по symlink/junction.
    Не раскрывает переменные окружения — это могло бы изменить смысл пути.
    """
    try:
        raw = Path(path)
    except (TypeError, ValueError):
        return None
    try:
        text = os.path.normpath(os.path.abspath(str(raw)))
        normalized = Path(text)
    except (OSError, ValueError, RuntimeError):
        return None
    if not str(normalized):
        return None
    return normalized


def path_components(path: Path | str) -> tuple[str, ...] | None:
    """Компоненты пути в нижнем регистре для безопасного сравнения на Windows."""
    normalized = normalize_windows_path(path)
    if normalized is None:
        return None
    parts: list[str] = []
    try:
        drive = normalized.drive.replace("/", "\\").rstrip("\\").casefold()
        rest = normalized.parts
        if drive:
            parts.append(drive)
            if rest:
                rest = rest[1:]
        for part in rest:
            name = str(part).strip("\\/")
            if not name:
                continue
            if name in {".", ".."}:
                return None
            parts.append(name.casefold())
    except (OSError, ValueError):
        return None
    if not parts:
        return None
    return tuple(parts)


def components_equal(left: Sequence[str], right: Sequence[str]) -> bool:
    return tuple(left) == tuple(right)


def is_component_prefix(parent: Sequence[str], child: Sequence[str]) -> bool:
    """True, если child равен parent или находится внутри parent целиком по компонентам."""
    if len(child) < len(parent):
        return False
    if not parent:
        return False
    return tuple(child[: len(parent)]) == tuple(parent)


def is_excluded_system_path(path: Path | str) -> bool:
    """Обязательные системные исключения. Нельзя отключить настройками."""
    components = path_components(path)
    if components is None:
        return True
    names = components[1:] if _looks_like_drive(components[0]) else components
    if names and names[0] in EXCLUDED_DRIVE_ROOT_DIR_NAMES:
        return True
    if not _looks_like_drive(components[0]) and names and names[0] in EXCLUDED_POSIX_ROOT_DIR_NAMES:
        return True
    for name in names:
        if name in EXCLUDED_DIR_NAMES_ANYWHERE:
            return True
        if name.startswith(".trash"):
            return True
        if name in EXCLUDED_SECURITY_PRODUCT_DIR_NAMES:
            return True
    if "windows" in names:
        for nested in ("system32", "syswow64", "winsxs", "servicing", "assembly"):
            if nested in names:
                return True
    return False


def _looks_like_drive(component: str) -> bool:
    return len(component) >= _DRIVE_ROOT_LENGTH and component[1] == ":"


def is_protected_filename(path: Path | str) -> bool:
    try:
        name = Path(path).name.casefold()
    except (TypeError, ValueError):
        return True
    return name in PROTECTED_FILE_NAMES


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except (OSError, ValueError):
        return None


def _stat_file_attributes(stat_result: os.stat_result) -> int:
    return int(getattr(stat_result, "st_file_attributes", 0) or 0)


def _exists_no_follow(path: Path) -> bool:
    """Существование без перехода по ссылке: достаточно успешного lstat."""
    return _lstat(path) is not None


def _is_symlink(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    return False


def _is_junction(path: Path) -> bool:
    try:
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and bool(is_junction()):
            return True
    except OSError:
        return True
    return False


def _is_reparse_point(path: Path, stat_result: os.stat_result | None = None) -> bool:
    if _is_symlink(path) or _is_junction(path):
        return True
    stats = stat_result if stat_result is not None else _lstat(path)
    if stats is None:
        return True
    attributes = _stat_file_attributes(stats)
    if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        return True
    return False


def _is_system_file(stat_result: os.stat_result) -> bool:
    return bool(_stat_file_attributes(stat_result) & FILE_ATTRIBUTE_SYSTEM)


def _is_regular_file_no_follow(path: Path) -> bool:
    stats = _lstat(path)
    if stats is None:
        return False
    if _is_symlink(path) or _is_reparse_point(path, stats):
        return False
    return stat.S_ISREG(stats.st_mode)


def _is_directory_no_follow(path: Path) -> bool:
    stats = _lstat(path)
    if stats is None:
        return False
    return stat.S_ISDIR(stats.st_mode)


def _fail(
    *,
    reason: str,
    normalized_path: Path,
    category: str | None = None,
    extension: str | None = None,
    is_symlink: bool = False,
    is_reparse_point: bool = False,
    size_bytes: int | None = None,
    mtime_ns: int | None = None,
    modified_timestamp: float | None = None,
) -> SafetyResult:
    return SafetyResult(
        safe=False,
        reason=reason,
        normalized_path=normalized_path,
        category=category,
        allows_index=False,
        allows_recycle=False,
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
        modified_timestamp=modified_timestamp,
        is_symlink=is_symlink,
        is_reparse_point=is_reparse_point,
        extension=extension,
    )


def _ok(
    *,
    normalized_path: Path,
    category: str,
    extension: str,
    purpose: str,
    explicitly_selected: bool,
    size_bytes: int,
    mtime_ns: int | None,
    modified_timestamp: float | None,
) -> SafetyResult:
    allows_index = True
    allows_recycle = explicitly_selected
    safe = allows_index if purpose != PURPOSE_RECYCLE else allows_recycle
    return SafetyResult(
        safe=safe,
        reason=REASON_OK if safe else REASON_NOT_SELECTED,
        normalized_path=normalized_path,
        category=category,
        allows_index=allows_index,
        allows_recycle=allows_recycle,
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
        modified_timestamp=modified_timestamp,
        is_symlink=False,
        is_reparse_point=False,
        extension=extension,
    )


def _safe_resolve(path: Path) -> Path | None:
    """Канонизация для проверки побега за scan roots. Не используется для обхода."""
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        try:
            return path.resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            return None


def _is_inside_any_root(child: Path, roots: Collection[Path]) -> bool:
    child_components = path_components(child)
    if child_components is None:
        return False
    for root in roots:
        root_components = path_components(root)
        if root_components is None:
            continue
        if is_component_prefix(root_components, child_components):
            return True
    return False


def _resolved_inside_any_root(child: Path, roots: Collection[Path]) -> bool:
    resolved_child = _safe_resolve(child)
    if resolved_child is None:
        return False
    child_components = path_components(resolved_child)
    if child_components is None:
        return False
    for root in roots:
        resolved_root = _safe_resolve(root)
        if resolved_root is None:
            continue
        root_components = path_components(resolved_root)
        if root_components is None:
            continue
        if is_component_prefix(root_components, child_components):
            return True
    return False


def _ancestor_reparse_is_forbidden(path: Path, scan_roots: Collection[Path]) -> bool:
    """Reparse у предка запрещён, кроме явно выбранного scan root.

    Это позволяет индексировать файлы в оболочечных папках, которые Windows
    перенаправляет (например Pictures → OneDrive), не входя в посторонние junction.
    """
    allowed_root_components: list[tuple[str, ...]] = []
    for root in scan_roots:
        components = path_components(root)
        if components is not None:
            allowed_root_components.append(components)
        resolved = _safe_resolve(Path(root))
        if resolved is not None:
            resolved_components = path_components(resolved)
            if resolved_components is not None:
                allowed_root_components.append(resolved_components)

    for ancestor in path.parents:
        try:
            if len(ancestor.parts) <= 1:
                continue
        except (OSError, ValueError):
            return True
        try:
            if not _exists_no_follow(ancestor):
                continue
        except OSError:
            return True
        if not _is_reparse_point(ancestor):
            continue
        ancestor_components = path_components(ancestor)
        if ancestor_components is None:
            return True
        allowed = False
        for root_components in allowed_root_components:
            if components_equal(ancestor_components, root_components):
                allowed = True
                break
        if not allowed:
            return True
    return False


def _metadata_matches(stat_result: os.stat_result, expected: ExpectedMetadata) -> bool:
    if int(stat_result.st_size) != int(expected.size_bytes):
        return False
    if expected.mtime_ns is not None:
        current_ns = int(getattr(stat_result, "st_mtime_ns", 0) or 0)
        return current_ns == int(expected.mtime_ns)
    if expected.modified_timestamp is not None:
        return float(stat_result.st_mtime) == float(expected.modified_timestamp)
    return True


class SafetyValidator:
    """Единственная точка политики безопасности для индексации и корзины."""

    def __init__(self, classifier: FileClassifier | None = None) -> None:
        self._classifier = classifier if classifier is not None else FileClassifier()

    @property
    def classifier(self) -> FileClassifier:
        return self._classifier

    def is_safe_media_file(
        self,
        path: Path,
        *,
        scan_roots: Collection[Path],
        explicitly_selected: bool = False,
        expected_metadata: ExpectedMetadata | None = None,
        expected_category: str | None = None,
        expected_path: Path | None = None,
        purpose: str = PURPOSE_INDEX,
    ) -> SafetyResult:
        fallback = Path(str(path)) if path is not None else Path()

        if path is None:
            return _fail(reason=REASON_INVALID_PATH, normalized_path=fallback)

        try:
            candidate = Path(path)
        except (TypeError, ValueError):
            return _fail(reason=REASON_INVALID_PATH, normalized_path=fallback)

        if not os.path.isabs(str(candidate)):
            normalized = normalize_windows_path(candidate)
            return _fail(
                reason=REASON_NOT_ABSOLUTE,
                normalized_path=normalized if normalized is not None else candidate,
            )

        normalized = normalize_windows_path(candidate)
        if normalized is None:
            return _fail(reason=REASON_INVALID_PATH, normalized_path=candidate)

        if expected_path is not None:
            expected_normalized = normalize_windows_path(expected_path)
            expected_components = (
                path_components(expected_normalized) if expected_normalized is not None else None
            )
            actual_components = path_components(normalized)
            if (
                expected_components is None
                or actual_components is None
                or not components_equal(expected_components, actual_components)
            ):
                return _fail(reason=REASON_PATH_CHANGED, normalized_path=normalized)

        roots = [Path(root) for root in scan_roots]
        if not roots:
            return _fail(reason=REASON_EMPTY_SCAN_ROOTS, normalized_path=normalized)

        if is_excluded_system_path(normalized):
            return _fail(reason=REASON_SYSTEM_PATH, normalized_path=normalized)

        if is_protected_filename(normalized):
            return _fail(reason=REASON_PROTECTED_NAME, normalized_path=normalized)

        extension = normalize_extension(normalized)
        if is_dangerous_extension(extension):
            return _fail(
                reason=REASON_DANGEROUS_EXTENSION,
                normalized_path=normalized,
                extension=extension,
            )

        category = self._classifier.classify(normalized)
        if category is None:
            return _fail(
                reason=REASON_UNKNOWN_EXTENSION,
                normalized_path=normalized,
                extension=extension,
            )

        if expected_category is not None and expected_category != category:
            return _fail(
                reason=REASON_CATEGORY_MISMATCH,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        try:
            exists = _exists_no_follow(normalized)
        except OSError:
            return _fail(reason=REASON_ACCESS, normalized_path=normalized, category=category)

        if not exists:
            return _fail(
                reason=REASON_MISSING,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        is_link = _is_symlink(normalized)
        is_reparse = _is_reparse_point(normalized)
        if is_link:
            return _fail(
                reason=REASON_SYMLINK,
                normalized_path=normalized,
                category=category,
                extension=extension,
                is_symlink=True,
                is_reparse_point=True,
            )
        if is_reparse:
            return _fail(
                reason=REASON_JUNCTION,
                normalized_path=normalized,
                category=category,
                extension=extension,
                is_symlink=False,
                is_reparse_point=True,
            )

        if _is_directory_no_follow(normalized) or not _is_regular_file_no_follow(normalized):
            return _fail(
                reason=REASON_NOT_A_FILE,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        if _ancestor_reparse_is_forbidden(normalized, roots):
            return _fail(
                reason=REASON_PARENT_REPARSE,
                normalized_path=normalized,
                category=category,
                extension=extension,
                is_reparse_point=True,
            )

        if not _is_inside_any_root(normalized, roots):
            return _fail(
                reason=REASON_OUTSIDE_SCAN_ROOT,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        if not _resolved_inside_any_root(normalized, roots):
            return _fail(
                reason=REASON_RESOLVED_ESCAPE,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        stats = _lstat(normalized)
        if stats is None:
            return _fail(
                reason=REASON_METADATA_UNAVAILABLE,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        if _is_system_file(stats):
            return _fail(
                reason=REASON_SYSTEM_ATTRIBUTE,
                normalized_path=normalized,
                category=category,
                extension=extension,
                size_bytes=int(stats.st_size),
                mtime_ns=int(getattr(stats, "st_mtime_ns", 0) or 0),
                modified_timestamp=float(stats.st_mtime),
            )

        try:
            size_bytes = int(stats.st_size)
            mtime_ns = int(getattr(stats, "st_mtime_ns", 0) or 0)
            modified_timestamp = float(stats.st_mtime)
        except (OSError, ValueError, OverflowError):
            return _fail(
                reason=REASON_METADATA_UNAVAILABLE,
                normalized_path=normalized,
                category=category,
                extension=extension,
            )

        if purpose == PURPOSE_RECYCLE:
            if not explicitly_selected:
                return _fail(
                    reason=REASON_NOT_SELECTED,
                    normalized_path=normalized,
                    category=category,
                    extension=extension,
                    size_bytes=size_bytes,
                    mtime_ns=mtime_ns,
                    modified_timestamp=modified_timestamp,
                )
            if expected_metadata is None:
                return _fail(
                    reason=REASON_MISSING_SCAN_SNAPSHOT,
                    normalized_path=normalized,
                    category=category,
                    extension=extension,
                    size_bytes=size_bytes,
                    mtime_ns=mtime_ns,
                    modified_timestamp=modified_timestamp,
                )

        if expected_metadata is not None and not _metadata_matches(stats, expected_metadata):
            return _fail(
                reason=REASON_FILE_CHANGED,
                normalized_path=normalized,
                category=category,
                extension=extension,
                size_bytes=size_bytes,
                mtime_ns=mtime_ns,
                modified_timestamp=modified_timestamp,
            )

        if expected_metadata is not None and expected_metadata.extension is not None:
            if normalize_extension(expected_metadata.extension) != extension:
                return _fail(
                    reason=REASON_FILE_CHANGED,
                    normalized_path=normalized,
                    category=category,
                    extension=extension,
                    size_bytes=size_bytes,
                    mtime_ns=mtime_ns,
                    modified_timestamp=modified_timestamp,
                )

        return _ok(
            normalized_path=normalized,
            category=category,
            extension=extension,
            purpose=purpose,
            explicitly_selected=explicitly_selected,
            size_bytes=size_bytes,
            mtime_ns=mtime_ns,
            modified_timestamp=modified_timestamp,
        )


_DEFAULT_VALIDATOR = SafetyValidator()


def is_safe_media_file(
    path: Path,
    *,
    scan_roots: Collection[Path],
    explicitly_selected: bool = False,
    expected_metadata: ExpectedMetadata | None = None,
    expected_category: str | None = None,
    expected_path: Path | None = None,
    purpose: str = PURPOSE_INDEX,
    validator: SafetyValidator | None = None,
) -> SafetyResult:
    """Публичная функция централизованной проверки.

    Для индексации передавайте ``purpose="index"``.
    Для корзины передавайте ``purpose="recycle"`` и ``explicitly_selected=True``.
    """
    active = validator if validator is not None else _DEFAULT_VALIDATOR
    return active.is_safe_media_file(
        path,
        scan_roots=scan_roots,
        explicitly_selected=explicitly_selected,
        expected_metadata=expected_metadata,
        expected_category=expected_category,
        expected_path=expected_path,
        purpose=purpose,
    )


def safety_status_from_result(result: SafetyResult) -> str:
    return SAFETY_STATUS_SAFE if result.safe or result.allows_index else SAFETY_STATUS_UNSAFE


def is_symlink_or_reparse(path: Path) -> bool:
    """True, если объект — symlink, junction или другая точка повторной обработки.

    При ошибке чтения атрибутов возвращает True (запрет входа).
    """
    try:
        return _is_reparse_point(Path(path))
    except OSError:
        return True


def is_hidden_entry(path: Path, stat_result: os.stat_result | None = None) -> bool:
    """Скрытый файл или каталог. Не используется для отключения системных исключений."""
    try:
        name = Path(path).name
    except (TypeError, ValueError):
        return True
    if name.startswith("."):
        return True
    stats = stat_result if stat_result is not None else _lstat(Path(path))
    if stats is None:
        return True
    return bool(_stat_file_attributes(stats) & FILE_ATTRIBUTE_HIDDEN)


def path_exists_no_follow(path: Path) -> bool:
    return _exists_no_follow(Path(path))


def is_directory_no_follow(path: Path) -> bool:
    return _is_directory_no_follow(Path(path))
