from __future__ import annotations

import math
import os
import re
from enum import Enum
from typing import Any


class ValidationError(ValueError):
    """Виняток для помилок валідації схеми або даних."""


class FieldType(str, Enum):
    INTEGER = "integer"
    REAL = "real"
    CHAR = "char"
    STRING = "string"
    TEXT_FILE = "text_file"
    INTEGER_INVL = "integerInvl"

    @classmethod
    def labels(cls) -> dict[str, str]:
        return {
            cls.INTEGER.value: "Ціле число (integer)",
            cls.REAL.value: "Дійсне число (real)",
            cls.CHAR.value: "Символ (char)",
            cls.STRING.value: "Рядок (string)",
            cls.TEXT_FILE.value: "Текстовий файл (text_file)",
            cls.INTEGER_INVL.value: "Цілочисловий інтервал (integerInvl)",
        }


_INVL_PATTERN = re.compile(r"^\s*\[?\s*(-?\d+)\s*(?:,|\.\.|;)\s*(-?\d+)\s*\]?\s*$")


def _parse_int(value: Any, field_name: str = "Значення") -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} має бути цілим числом, а не bool.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValidationError(f"{field_name} не може бути порожнім.")
        try:
            return int(text)
        except ValueError as exc:
            raise ValidationError(f"'{value}' не є коректним цілим числом.") from exc
    raise ValidationError(f"Очікується ціле число, отримано {type(value).__name__}.")


def validate_value(field_type: FieldType | str, value: Any) -> Any:
    """Валідує значення відповідно до типу поля та повертає нормалізоване представлення."""
    if isinstance(field_type, str):
        try:
            field_type = FieldType(field_type)
        except ValueError as exc:
            raise ValidationError(f"Невідомий тип даних: '{field_type}'.") from exc

    if field_type == FieldType.INTEGER:
        return _parse_int(value)

    if field_type == FieldType.REAL:
        if isinstance(value, bool):
            raise ValidationError("Дійсне число не може бути типу bool.")
        if isinstance(value, (int, float)):
            num = float(value)
        elif isinstance(value, str):
            text = value.strip().replace(",", ".")
            if not text:
                raise ValidationError("Поле дійсного числа не може бути порожнім.")
            try:
                num = float(text)
            except ValueError as exc:
                raise ValidationError(f"'{value}' не є коректним дійсним числом.") from exc
        else:
            raise ValidationError(f"Очікується дійсне число, отримано {type(value).__name__}.")

        if not math.isfinite(num):
            raise ValidationError("Дійсне число не може бути NaN або нескінченністю.")
        return num

    if field_type == FieldType.CHAR:
        if not isinstance(value, str):
            raise ValidationError("Значення типу char має бути рядком.")
        if len(value) != 1:
            raise ValidationError(f"Тип char вимагає рівно 1 символ (отримано {len(value)}).")
        return value

    if field_type == FieldType.STRING:
        if not isinstance(value, str):
            raise ValidationError("Значення типу string має бути рядком.")
        return value

    if field_type == FieldType.INTEGER_INVL:
        if isinstance(value, dict):
            if "min" not in value or "max" not in value:
                raise ValidationError("Інтервал має містити ключі 'min' та 'max'.")
            min_val = _parse_int(value["min"], "Нижня межа інтервалу")
            max_val = _parse_int(value["max"], "Верхня межа інтервалу")
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            min_val = _parse_int(value[0], "Нижня межа інтервалу")
            max_val = _parse_int(value[1], "Верхня межа інтервалу")
        elif isinstance(value, str):
            match = _INVL_PATTERN.match(value)
            if not match:
                raise ValidationError(
                    "Некоректний формат integerInvl. Використовуйте формат '[min, max]' або 'min..max'."
                )
            min_val = int(match.group(1))
            max_val = int(match.group(2))
        else:
            raise ValidationError("Очікується інтервал формату '[min, max]'.")

        if min_val > max_val:
            raise ValidationError(
                f"Нижня межа інтервалу ({min_val}) не може перевищувати верхню ({max_val})."
            )
        return {"min": min_val, "max": max_val}

    if field_type == FieldType.TEXT_FILE:
        if not isinstance(value, dict):
            raise ValidationError("Текстовий файл має бути представлений як {'filename': ..., 'content': ...}.")
        filename = value.get("filename")
        content = value.get("content")
        if not isinstance(filename, str) or not filename.strip():
            raise ValidationError("Назва текстового файлу не може бути порожньою.")
        if not isinstance(content, str):
            raise ValidationError("Вміст текстового файлу має бути текстом (str).")
        if "\x00" in content:
            raise ValidationError("Файл містить бінарні дані (нульові байти) і не є текстовим.")
        return {"filename": os.path.basename(filename.strip()), "content": content}

    raise ValidationError(f"Непідтримуваний тип даних: {field_type}")


def load_text_file_from_disk(filepath: str) -> dict[str, str]:
    """Зчитує текстовий файл з диска та перевіряє, що він коректний UTF-8 текст."""
    if not os.path.isfile(filepath):
        raise ValidationError(f"Файл '{filepath}' не знайдено.")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"Файл '{os.path.basename(filepath)}' не є текстовим файлом у кодуванні UTF-8."
        ) from exc
    return validate_value(
        FieldType.TEXT_FILE,
        {"filename": os.path.basename(filepath), "content": content},
    )


def format_value(field_type: FieldType | str, value: Any) -> str:
    """Форматує значення для зручного відображення в таблиці GUI / Web."""
    if isinstance(field_type, str):
        field_type = FieldType(field_type)
    if field_type == FieldType.INTEGER_INVL and isinstance(value, dict):
        return f"[{value['min']}, {value['max']}]"
    if field_type == FieldType.TEXT_FILE and isinstance(value, dict):
        preview_len = len(value.get("content", ""))
        return f"{value['filename']} ({preview_len} симв.)"
    return str(value)