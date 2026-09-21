"""Экспорт отчёта по найденным файлам. Не изменяет исходные файлы."""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from app.constants import APP_NAME, APP_VERSION
from app.paths import ensure_user_dirs, reports_dir
from models.media_file import MediaFile
from models.media_table_model import format_size_bytes

logger = logging.getLogger("media_disk_cleaner.report")

CSV_COLUMNS = (
    "name",
    "category",
    "extension",
    "size_bytes",
    "size_label",
    "modified",
    "created",
    "path",
    "drive",
    "selected",
)


class ReportService:
    def export_scan(
        self,
        files: Sequence[MediaFile],
        *,
        destination_dir: Path | None = None,
    ) -> tuple[Path, Path]:
        ensure_user_dirs()
        folder = destination_dir if destination_dir is not None else reports_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = folder / f"scan_{stamp}.csv"
        json_path = folder / f"scan_{stamp}.json"
        self._write_csv(csv_path, files)
        self._write_json(json_path, files)
        logger.info("Exported report CSV=%s JSON=%s", csv_path, json_path)
        return csv_path, json_path

    def _write_csv(self, path: Path, files: Sequence[MediaFile]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for item in files:
                writer.writerow(
                    {
                        "name": item.name,
                        "category": item.category,
                        "extension": item.extension,
                        "size_bytes": item.size_bytes,
                        "size_label": format_size_bytes(item.size_bytes),
                        "modified": _iso(item.modified_at),
                        "created": _iso(item.created_at),
                        "path": str(item.normalized_path),
                        "drive": item.drive,
                        "selected": "yes" if item.is_selected else "no",
                    }
                )

    def _write_json(self, path: Path, files: Sequence[MediaFile]) -> None:
        image = sum(1 for item in files if item.category == "image")
        video = sum(1 for item in files if item.category == "video")
        audio = sum(1 for item in files if item.category == "audio")
        total = sum(item.size_bytes for item in files)
        payload = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "summary": {
                "files": len(files),
                "total_size_bytes": total,
                "total_size_label": format_size_bytes(total),
                "image_count": image,
                "video_count": video,
                "audio_count": audio,
            },
            "files": [
                {
                    "name": item.name,
                    "category": item.category,
                    "extension": item.extension,
                    "size_bytes": item.size_bytes,
                    "modified": _iso(item.modified_at),
                    "created": _iso(item.created_at),
                    "path": str(item.normalized_path),
                    "drive": item.drive,
                    "selected": bool(item.is_selected),
                }
                for item in files
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat(timespec="seconds")
