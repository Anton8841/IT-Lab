from __future__ import annotations

import json
from pathlib import Path

from .models import Database
from .types import ValidationError


def save_database(db: Database, filepath: str | Path) -> None:
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db.to_dict(), f, ensure_ascii=False, indent=2)


def load_database(filepath: str | Path) -> Database:
    path = Path(filepath)
    if not path.is_file():
        raise ValidationError(f"Файл бази даних '{path}' не знайдено.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Помилка читання JSON-файлу '{path.name}': {exc}") from exc

    return Database.from_dict(data)