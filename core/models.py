from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import FieldType, ValidationError, validate_value


def _make_hashable(value: Any) -> Any:
    """Перетворює нормалізоване значення (включно зі словниками) на hashable-ключ."""
    if isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_make_hashable(item) for item in value)
    return value


@dataclass
class Column:
    name: str
    field_type: FieldType

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Назва стовпця не може бути порожньою.")
        self.name = self.name.strip()

        if isinstance(self.field_type, str):
            try:
                self.field_type = FieldType(self.field_type)
            except ValueError as exc:
                raise ValidationError(f"Невідомий тип поля: '{self.field_type}'.") from exc
        elif not isinstance(self.field_type, FieldType):
            raise ValidationError("Некоректний тип поля.")

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "field_type": self.field_type.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Column:
        return cls(name=data["name"], field_type=FieldType(data["field_type"]))


@dataclass
class Table:
    name: str
    columns: list[Column]
    rows: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Назва таблиці не може бути порожньою.")
        self.name = self.name.strip()

        if not self.columns:
            raise ValidationError("Таблиця повинна містити хоча б одне поле.")

        seen_names: set[str] = set()
        for col in self.columns:
            if col.name in seen_names:
                raise ValidationError(f"Дублювання назви поля '{col.name}' у таблиці '{self.name}'.")
            seen_names.add(col.name)

    def validate_row(self, row_data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(row_data, dict):
            raise ValidationError("Рядок має бути переданий як словник {назва_поля: значення}.")

        expected_names = {col.name for col in self.columns}
        extra_keys = set(row_data.keys()) - expected_names
        if extra_keys:
            raise ValidationError(f"Невідомі поля в рядку: {', '.join(sorted(extra_keys))}.")

        validated: dict[str, Any] = {}
        for col in self.columns:
            if col.name not in row_data:
                raise ValidationError(f"Відсутнє значення для обов'язкового поля '{col.name}'.")
            try:
                validated[col.name] = validate_value(col.field_type, row_data[col.name])
            except ValidationError as exc:
                raise ValidationError(f"Поле '{col.name}': {exc}") from exc

        return validated

    def add_row(self, row_data: dict[str, Any]) -> dict[str, Any]:
        validated = self.validate_row(row_data)
        self.rows.append(validated)
        return validated

    def edit_row(self, index: int, row_data: dict[str, Any]) -> dict[str, Any]:
        if not (0 <= index < len(self.rows)):
            raise ValidationError(f"Рядок із індексом {index} не існує.")
        validated = self.validate_row(row_data)
        self.rows[index] = validated
        return validated

    def delete_row(self, index: int) -> None:
        if not (0 <= index < len(self.rows)):
            raise ValidationError(f"Рядок із індексом {index} не існує.")
        self.rows.pop(index)

    def remove_duplicates(self) -> int:
       
        seen: set[tuple[Any, ...]] = set()
        unique_rows: list[dict[str, Any]] = []
        removed_count = 0

        for row in self.rows:
            row_key = tuple((col.name, _make_hashable(row[col.name])) for col in self.columns)
            if row_key in seen:
                removed_count += 1
            else:
                seen.add(row_key)
                unique_rows.append(row)

        self.rows = unique_rows
        return removed_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "columns": [col.to_dict() for col in self.columns],
            "rows": self.rows,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Table:
        columns = [Column.from_dict(c) for c in data["columns"]]
        table = cls(name=data["name"], columns=columns)
        for row in data.get("rows", []):
            table.add_row(row)
        return table


class Database:
    def __init__(self, name: str = "Нова база даних") -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Назва бази даних не може бути порожньою.")
        self.name: str = name.strip()
        self.tables: dict[str, Table] = {}

    def create_table(self, name: str, columns: list[Column]) -> Table:
        clean_name = name.strip() if isinstance(name, str) else ""
        if clean_name in self.tables:
            raise ValidationError(f"Таблиця з назвою '{clean_name}' вже існує.")
        table = Table(name=clean_name, columns=columns)
        self.tables[table.name] = table
        return table

    def delete_table(self, name: str) -> None:
        if name not in self.tables:
            raise ValidationError(f"Таблицю '{name}' не знайдено.")
        del self.tables[name]

    def get_table(self, name: str) -> Table:
        if name not in self.tables:
            raise ValidationError(f"Таблицю '{name}' не знайдено.")
        return self.tables[name]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tables": [table.to_dict() for table in self.tables.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Database:
        if not isinstance(data, dict) or "name" not in data or "tables" not in data:
            raise ValidationError("Некоректна структура файлу бази даних.")
        db = cls(name=data["name"])
        for t_data in data["tables"]:
            table = Table.from_dict(t_data)
            if table.name in db.tables:
                raise ValidationError(f"У файлі виявлено дублювання таблиці '{table.name}'.")
            db.tables[table.name] = table
        return db