import tempfile
import unittest
from pathlib import Path

from core import (
    Column,
    Database,
    FieldType,
    ValidationError,
    load_database,
    save_database,
    validate_value,
)


class TestTableDBMS(unittest.TestCase):
    def test_integer_interval_validation(self) -> None:
        """Тест валідації додаткового типу integerInvl."""
        self.assertEqual(
            validate_value(FieldType.INTEGER_INVL, "[1, 10]"),
            {"min": 1, "max": 10},
        )
        self.assertEqual(
            validate_value(FieldType.INTEGER_INVL, "-5..5"),
            {"min": -5, "max": 5},
        )
        # Некоректний інтервал (min > max)
        with self.assertRaises(ValidationError):
            validate_value(FieldType.INTEGER_INVL, "[15, 3]")
        # Некоректний формат
        with self.assertRaises(ValidationError):
            validate_value(FieldType.INTEGER_INVL, "abc")

    def test_create_table_and_row_validation(self) -> None:
        """Тест створення таблиці, додавання та редагування рядків із валідацією."""
        db = Database("TestDB")
        table = db.create_table(
            "Students",
            [
                Column("id", FieldType.INTEGER),
                Column("gpa", FieldType.REAL),
                Column("grade", FieldType.CHAR),
                Column("name", FieldType.STRING),
                Column("bio", FieldType.TEXT_FILE),
            ],
        )

        table.add_row(
            {
                "id": "1",
                "gpa": "95.5",
                "grade": "A",
                "name": "Олег",
                "bio": {"filename": "oleg.txt", "content": "Студент 3 курсу"},
            }
        )
        self.assertEqual(table.rows[0]["id"], 1)
        self.assertEqual(table.rows[0]["gpa"], 95.5)

        # Помилка валідації char (більше 1 символу)
        with self.assertRaises(ValidationError):
            table.add_row(
                {
                    "id": 2,
                    "gpa": 80.0,
                    "grade": "AB",
                    "name": "Іван",
                    "bio": {"filename": "ivan.txt", "content": "..."},
                }
            )

        # Редагування рядка
        table.edit_row(
            0,
            {
                "id": 1,
                "gpa": 98.0,
                "grade": "A",
                "name": "Олег К.",
                "bio": {"filename": "oleg.txt", "content": "Оновлено"},
            },
        )
        self.assertEqual(table.rows[0]["name"], "Олег К.")

    def test_remove_duplicates_operation(self) -> None:
        """Тест індивідуальної операції (варіант 5): вилучення повторюваних рядків."""
        db = Database("ShopDB")
        table = db.create_table(
            "Items",
            [
                Column("code", FieldType.INTEGER),
                Column("title", FieldType.STRING),
                Column("range", FieldType.INTEGER_INVL),
                Column("note", FieldType.TEXT_FILE),
            ],
        )

        row_a = {
            "code": 101,
            "title": "Товар А",
            "range": "[1, 5]",
            "note": {"filename": "a.txt", "content": "Опис А"},
        }
        row_b = {
            "code": 202,
            "title": "Товар Б",
            "range": "[10, 20]",
            "note": {"filename": "b.txt", "content": "Опис Б"},
        }
        # Той самий рядок_а, але інтервал введено в іншому форматі "1..5"
        row_a_duplicate = {
            "code": "101",
            "title": "Товар А",
            "range": "1..5",
            "note": {"filename": "a.txt", "content": "Опис А"},
        }

        table.add_row(row_a)
        table.add_row(row_b)
        table.add_row(row_a_duplicate)
        table.add_row(row_b)

        removed = table.remove_duplicates()

        self.assertEqual(removed, 2)
        self.assertEqual(len(table.rows), 2)
        self.assertEqual(table.rows[0]["code"], 101)
        self.assertEqual(table.rows[1]["code"], 202)

    def test_save_and_load_database(self) -> None:
        """Тест збереження бази на диск та зчитування з диска."""
        db = Database("PersistedDB")
        table = db.create_table(
            "Logs",
            [
                Column("level", FieldType.CHAR),
                Column("span", FieldType.INTEGER_INVL),
                Column("file", FieldType.TEXT_FILE),
            ],
        )
        table.add_row(
            {
                "level": "I",
                "span": "[0, 100]",
                "file": {"filename": "log.txt", "content": "OK"},
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_db.json"
            save_database(db, db_path)
            loaded_db = load_database(db_path)

        self.assertEqual(loaded_db.name, "PersistedDB")
        loaded_table = loaded_db.get_table("Logs")
        self.assertEqual(len(loaded_table.rows), 1)
        self.assertEqual(loaded_table.rows[0]["span"], {"min": 0, "max": 100})
        self.assertEqual(loaded_table.rows[0]["file"]["content"], "OK")

    def test_table_deletion_and_duplicate_table_name(self) -> None:
        """Тест валідації назв таблиць та знищення таблиці."""
        db = Database("DB")
        db.create_table("Users", [Column("id", FieldType.INTEGER)])

        with self.assertRaises(ValidationError):
            db.create_table("Users", [Column("id", FieldType.INTEGER)])

        db.delete_table("Users")
        self.assertEqual(len(db.tables), 0)


if __name__ == "__main__":
    unittest.main()