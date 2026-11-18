from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

from core import (
    Column,
    Database,
    FieldType,
    Table,
    ValidationError,
    format_value,
    load_database,
    load_text_file_from_disk,
    save_database,
)


class CreateTableDialog(tk.Toplevel):
    """Модальне вікно для створення нової таблиці з валідацією схеми."""

    def __init__(self, parent: tk.Misc, db: Database) -> None:
        super().__init__(parent)
        self.db = db
        self.created_table: Table | None = None
        self._columns: list[Column] = []

        self.title("Створення нової таблиці")
        self.geometry("560x440")
        self.minsize(500, 380)
        self.transient(parent)
        self.grab_set()

        self._type_labels = FieldType.labels()
        self._label_to_type = {label: ft for ft, label in self._type_labels.items()}

        self._build_ui()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        # Назва таблиці
        name_frame = ttk.Frame(container)
        name_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(name_frame, text="Назва таблиці:", width=16).pack(side=tk.LEFT)
        self.table_name_var = tk.StringVar()
        name_entry = ttk.Entry(name_frame, textvariable=self.table_name_var)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_entry.focus_set()

        # Блок додавання поля
        add_box = ttk.LabelFrame(container, text="Додати поле (стовпець)", padding=10)
        add_box.pack(fill=tk.X, pady=(0, 10))

        row1 = ttk.Frame(add_box)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Назва поля:").pack(side=tk.LEFT, padx=(0, 6))
        self.col_name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.col_name_var, width=18).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10)
        )

        ttk.Label(row1, text="Тип:").pack(side=tk.LEFT, padx=(0, 6))
        self.col_type_var = tk.StringVar(value=list(self._label_to_type.keys())[0])
        type_combo = ttk.Combobox(
            row1,
            textvariable=self.col_type_var,
            values=list(self._label_to_type.keys()),
            state="readonly",
            width=28,
        )
        type_combo.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(row1, text="+ Додати", command=self._add_column).pack(side=tk.LEFT)

        # Список доданих полів
        list_frame = ttk.LabelFrame(container, text="Поля таблиці", padding=8)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.cols_tree = ttk.Treeview(
            list_frame, columns=("name", "type"), show="headings", height=7
        )
        self.cols_tree.heading("name", text="Назва поля")
        self.cols_tree.heading("type", text="Тип даних")
        self.cols_tree.column("name", width=220)
        self.cols_tree.column("type", width=260)

        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.cols_tree.yview)
        self.cols_tree.configure(yscrollcommand=sb.set)
        self.cols_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Кнопки знизу
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X)

        ttk.Button(
            btn_frame, text="Видалити вибране поле", command=self._remove_selected_column
        ).pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="Скасувати", command=self.destroy).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(btn_frame, text="Створити таблицю", command=self._create_table).pack(
            side=tk.RIGHT
        )

    def _add_column(self) -> None:
        col_name = self.col_name_var.get().strip()
        type_label = self.col_type_var.get()
        field_type = FieldType(self._label_to_type[type_label])

        try:
            col = Column(name=col_name, field_type=field_type)
        except ValidationError as exc:
            messagebox.showerror("Помилка валідації поля", str(exc), parent=self)
            return

        if any(c.name == col.name for c in self._columns):
            messagebox.showerror(
                "Помилка", f"Поле з назвою '{col.name}' вже додано.", parent=self
            )
            return

        self._columns.append(col)
        self.cols_tree.insert("", tk.END, values=(col.name, self._type_labels[col.field_type.value]))
        self.col_name_var.set("")

    def _remove_selected_column(self) -> None:
        selected = self.cols_tree.selection()
        if not selected:
            return
        idx = self.cols_tree.index(selected[0])
        self._columns.pop(idx)
        self.cols_tree.delete(selected[0])

    def _create_table(self) -> None:
        table_name = self.table_name_var.get()
        try:
            self.created_table = self.db.create_table(table_name, list(self._columns))
        except ValidationError as exc:
            messagebox.showerror("Помилка створення таблиці", str(exc), parent=self)
            return
        self.destroy()


class RowEditorDialog(tk.Toplevel):
    """Модальне вікно для створення та редагування рядка таблиці з прокруткою."""

    def __init__(
        self,
        parent: tk.Misc,
        table: Table,
        row_index: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.table = table
        self.row_index = row_index
        self.saved = False

        is_edit = row_index is not None
        self.title("Редагування рядка" if is_edit else "Додавання нового рядка")
        self.geometry("560x480")
        self.minsize(480, 360)
        self.transient(parent)
        self.grab_set()

        self._inputs: dict[str, Any] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Прокручувана область для необмеженої кількості полів
        canvas = tk.Canvas(main_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        form_frame = ttk.Frame(canvas, padding=(4, 4, 12, 4))

        form_window = canvas.create_window((0, 0), window=form_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        form_frame.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>", lambda e: canvas.itemconfig(form_window, width=e.width)
        )

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        existing_row = (
            self.table.rows[self.row_index] if self.row_index is not None else {}
        )

        for col in self.table.columns:
            field_box = ttk.LabelFrame(
                form_frame,
                text=f"{col.name}  [{col.field_type.value}]",
                padding=8,
            )
            field_box.pack(fill=tk.X, pady=(0, 8))

            initial_val = existing_row.get(col.name)

            if col.field_type == FieldType.TEXT_FILE:
                top_row = ttk.Frame(field_box)
                top_row.pack(fill=tk.X, pady=(0, 6))

                ttk.Label(top_row, text="Ім'я файлу:").pack(side=tk.LEFT, padx=(0, 6))
                fname_var = tk.StringVar(
                    value=initial_val["filename"] if isinstance(initial_val, dict) else "file.txt"
                )
                ttk.Entry(top_row, textvariable=fname_var).pack(
                    side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
                )

                text_widget = tk.Text(field_box, height=4, wrap=tk.WORD)
                text_widget.pack(fill=tk.X, expand=True)
                if isinstance(initial_val, dict):
                    text_widget.insert("1.0", initial_val.get("content", ""))

                def pick_file(
                    f_var: tk.StringVar = fname_var, t_widget: tk.Text = text_widget
                ) -> None:
                    path = filedialog.askopenfilename(
                        parent=self,
                        title="Оберіть текстовий файл",
                        filetypes=[("Текстові файли", "*.txt *.md *.csv *.log"), ("Усі файли", "*.*")],
                    )
                    if not path:
                        return
                    try:
                        loaded = load_text_file_from_disk(path)
                    except ValidationError as exc:
                        messagebox.showerror("Помилка файлу", str(exc), parent=self)
                        return
                    f_var.set(loaded["filename"])
                    t_widget.delete("1.0", tk.END)
                    t_widget.insert("1.0", loaded["content"])

                ttk.Button(top_row, text="Обрати з диска...", command=pick_file).pack(
                    side=tk.LEFT
                )
                self._inputs[col.name] = ("text_file", fname_var, text_widget)
            else:
                hint = self._get_hint(col.field_type)
                if hint:
                    ttk.Label(field_box, text=hint, foreground="#555555").pack(
                        anchor="w", pady=(0, 4)
                    )

                str_var = tk.StringVar()
                if initial_val is not None:
                    if col.field_type == FieldType.INTEGER_INVL and isinstance(initial_val, dict):
                        str_var.set(f"[{initial_val['min']}, {initial_val['max']}]")
                    else:
                        str_var.set(str(initial_val))

                ttk.Entry(field_box, textvariable=str_var).pack(fill=tk.X)
                self._inputs[col.name] = ("scalar", str_var)

        # Кнопки дій
        btn_bar = ttk.Frame(self, padding=(10, 6, 10, 10))
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="Скасувати", command=self.destroy).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(btn_bar, text="Зберегти", command=self._save).pack(side=tk.RIGHT)

    @staticmethod
    def _get_hint(field_type: FieldType) -> str:
        hints = {
            FieldType.INTEGER: "Ціле число (напр. 42 або -7)",
            FieldType.REAL: "Дійсне число (напр. 3.14)",
            FieldType.CHAR: "Рівно 1 символ (напр. A)",
            FieldType.STRING: "Довільний текстовий рядок",
            FieldType.INTEGER_INVL: "Інтервал цілих чисел: [min, max] або min..max (напр. [1, 10])",
        }
        return hints.get(field_type, "")

    def _save(self) -> None:
        row_data: dict[str, Any] = {}
        for col in self.table.columns:
            inp = self._inputs[col.name]
            if inp[0] == "text_file":
                _, fname_var, text_widget = inp
                row_data[col.name] = {
                    "filename": fname_var.get(),
                    "content": text_widget.get("1.0", "end-1c"),
                }
            else:
                _, str_var = inp
                row_data[col.name] = str_var.get()

        try:
            if self.row_index is None:
                self.table.add_row(row_data)
            else:
                self.table.edit_row(self.row_index, row_data)
        except ValidationError as exc:
            messagebox.showerror("Помилка валідації даних", str(exc), parent=self)
            return

        self.saved = True
        self.destroy()


class TextFileViewerDialog(tk.Toplevel):
    """Вікно перегляду вмісту полів типу text_file у вибраному рядку."""

    def __init__(self, parent: tk.Misc, table: Table, row_index: int) -> None:
        super().__init__(parent)
        self.title(f"Текстові файли — рядок #{row_index + 1}")
        self.geometry("560x420")
        self.transient(parent)

        container = ttk.Frame(self, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        row = table.rows[row_index]
        text_cols = [c for c in table.columns if c.field_type == FieldType.TEXT_FILE]

        notebook = ttk.Notebook(container)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        for col in text_cols:
            file_data = row[col.name]
            tab = ttk.Frame(notebook, padding=8)
            notebook.add(tab, text=f"{col.name}: {file_data['filename']}")

            txt = tk.Text(tab, wrap=tk.WORD)
            sb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            txt.insert("1.0", file_data["content"])
            txt.configure(state=tk.DISABLED)

            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(container, text="Закрити", command=self.destroy).pack(anchor="e")


class TableDBMSApp(tk.Tk):
    """Головне вікно десктоп-версії системи управління табличними БД."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Таблична СУБД — Варіант 1 / 5 (Desktop)")
        self.geometry("1040x640")
        self.minsize(840, 500)

        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.db = Database("Моя база даних")
        self.current_file: Path | None = None
        self.current_table_name: str | None = None
        self.is_dirty = False

        self._build_menu()
        self._build_ui()
        self._refresh_all()

        self.protocol("WM_DELETE_WINDOW", self._on_exit)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Нова база даних", command=self._new_database)
        file_menu.add_command(label="Відкрити базу з диска...", command=self._open_database)
        file_menu.add_separator()
        file_menu.add_command(label="Зберегти базу", command=self._save_database)
        file_menu.add_command(label="Зберегти базу як...", command=self._save_database_as)
        file_menu.add_separator()
        file_menu.add_command(label="Вихід", command=self._on_exit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        table_menu = tk.Menu(menubar, tearoff=False)
        table_menu.add_command(label="Створити таблицю...", command=self._create_table)
        table_menu.add_command(label="Видалити поточну таблицю", command=self._delete_table)
        menubar.add_cascade(label="Таблиця", menu=table_menu)

        ops_menu = tk.Menu(menubar, tearoff=False)
        ops_menu.add_command(
            label="Вилучити повторювані рядки (Варіант 5)",
            command=self._remove_duplicates,
        )
        menubar.add_cascade(label="Операції", menu=ops_menu)

        self.config(menu=menubar)

    def _build_ui(self) -> None:
        # Верхня панель швидких дій БД
        top_bar = ttk.Frame(self, padding=(10, 8))
        top_bar.pack(fill=tk.X)

        ttk.Button(top_bar, text="Нова БД", command=self._new_database).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(top_bar, text="Відкрити БД...", command=self._open_database).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(top_bar, text="Зберегти БД", command=self._save_database).pack(
            side=tk.LEFT, padx=(0, 12)
        )

        self.db_info_var = tk.StringVar()
        ttk.Label(
            top_bar, textvariable=self.db_info_var, font=("TkDefaultFont", 10, "bold")
        ).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Основна робоча область (зліва список таблиць, справа вміст таблиці)
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        # Ліва панель
        left_frame = ttk.LabelFrame(paned, text="Таблиці БД", padding=8)
        paned.add(left_frame, weight=1)

        list_container = ttk.Frame(left_frame)
        list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.tables_listbox = tk.Listbox(list_container, exportselection=False, width=24)
        lb_scroll = ttk.Scrollbar(
            list_container, orient=tk.VERTICAL, command=self.tables_listbox.yview
        )
        self.tables_listbox.configure(yscrollcommand=lb_scroll.set)
        self.tables_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tables_listbox.bind("<<ListboxSelect>>", self._on_table_select)

        left_btns = ttk.Frame(left_frame)
        left_btns.pack(fill=tk.X)
        ttk.Button(left_btns, text="+ Створити", command=self._create_table).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4)
        )
        ttk.Button(left_btns, text="- Видалити", command=self._delete_table).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # Права панель
        right_frame = ttk.Frame(paned, padding=(6, 0, 0, 0))
        paned.add(right_frame, weight=4)

        self.table_header_var = tk.StringVar(value="Таблиця не вибрана")
        ttk.Label(
            right_frame,
            textvariable=self.table_header_var,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        # Кнопки дій над рядками
        row_toolbar = ttk.Frame(right_frame)
        row_toolbar.pack(fill=tk.X, pady=(0, 8))

        self.btn_add_row = ttk.Button(
            row_toolbar, text="+ Додати рядок", command=self._add_row
        )
        self.btn_add_row.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_edit_row = ttk.Button(
            row_toolbar, text="Редагувати рядок", command=self._edit_row
        )
        self.btn_edit_row.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_del_row = ttk.Button(
            row_toolbar, text="Видалити рядок", command=self._delete_row
        )
        self.btn_del_row.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_view_files = ttk.Button(
            row_toolbar, text="Переглянути текстові файли", command=self._view_text_files
        )
        self.btn_view_files.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_dedup = ttk.Button(
            row_toolbar,
            text="Вилучити повторювані рядки",
            command=self._remove_duplicates,
        )
        self.btn_dedup.pack(side=tk.RIGHT)

        # Таблиця даних (Treeview)
        tree_wrap = ttk.Frame(right_frame)
        tree_wrap.pack(fill=tk.BOTH, expand=True)

        self.data_tree = ttk.Treeview(tree_wrap, show="headings", selectmode="browse")
        y_sb = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL, command=self.data_tree.yview)
        x_sb = ttk.Scrollbar(tree_wrap, orient=tk.HORIZONTAL, command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=y_sb.set, xscrollcommand=x_sb.set)

        self.data_tree.grid(row=0, column=0, sticky="nsew")
        y_sb.grid(row=0, column=1, sticky="ns")
        x_sb.grid(row=1, column=0, sticky="ew")
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.data_tree.bind("<Double-1>", lambda _e: self._edit_row())

        # Рядок статусу
        self.status_var = tk.StringVar(value="Готово до роботи.")
        status_bar = ttk.Label(
            self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=(8, 3)
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ---- Оновлення інтерфейсу ----

    def _refresh_all(self) -> None:
        file_label = str(self.current_file) if self.current_file else "не збережено на диск"
        dirty_mark = " *" if self.is_dirty else ""
        self.db_info_var.set(f"БД: {self.db.name}{dirty_mark}  |  Файл: {file_label}")

        self.tables_listbox.delete(0, tk.END)
        table_names = list(self.db.tables.keys())
        for name in table_names:
            self.tables_listbox.insert(tk.END, name)

        if self.current_table_name not in self.db.tables:
            self.current_table_name = table_names[0] if table_names else None

        if self.current_table_name is not None:
            idx = table_names.index(self.current_table_name)
            self.tables_listbox.selection_set(idx)
            self.tables_listbox.activate(idx)

        self._refresh_table_view()

    def _refresh_table_view(self) -> None:
        self.data_tree.delete(*self.data_tree.get_children())

        if self.current_table_name is None:
            self.data_tree["columns"] = ()
            self.table_header_var.set("Оберіть або створіть таблицю")
            self._set_row_buttons_state(enabled=False, has_text_files=False)
            return

        table = self.db.get_table(self.current_table_name)
        self.table_header_var.set(
            f"Таблиця: {table.name}   |   Полів: {len(table.columns)}   |   Рядків: {len(table.rows)}"
        )

        col_ids = ["#"] + [col.name for col in table.columns]
        self.data_tree["columns"] = col_ids

        self.data_tree.heading("#", text="#")
        self.data_tree.column("#", width=45, minwidth=40, stretch=False, anchor="center")

        for col in table.columns:
            self.data_tree.heading(col.name, text=f"{col.name} ({col.field_type.value})")
            self.data_tree.column(col.name, width=150, minwidth=100, anchor="w")

        for idx, row in enumerate(table.rows):
            values = [str(idx + 1)]
            for col in table.columns:
                formatted = format_value(col.field_type, row[col.name])
                # Прибираємо переноси рядка для охайного вигляду в комірці
                values.append(formatted.replace("\n", " "))
            self.data_tree.insert("", tk.END, iid=str(idx), values=values)

        has_text = any(c.field_type == FieldType.TEXT_FILE for c in table.columns)
        self._set_row_buttons_state(enabled=True, has_text_files=has_text)

    def _set_row_buttons_state(self, enabled: bool, has_text_files: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_add_row.configure(state=state)
        self.btn_edit_row.configure(state=state)
        self.btn_del_row.configure(state=state)
        self.btn_dedup.configure(state=state)
        self.btn_view_files.configure(
            state=tk.NORMAL if (enabled and has_text_files) else tk.DISABLED
        )

    # ---- Операції з БД ----

    def _confirm_discard_if_dirty(self) -> bool:
        if not self.is_dirty:
            return True
        ans = messagebox.askyesnocancel(
            "Незбережені зміни",
            "У поточній базі даних є незбережені зміни. Зберегти перед продовженням?",
            parent=self,
        )
        if ans is None:
            return False
        if ans is True:
            return self._save_database()
        return True

    def _new_database(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        name = simpledialog.askstring(
            "Нова база даних",
            "Введіть назву нової бази даних:",
            initialvalue="MyDatabase",
            parent=self,
        )
        if name is None:
            return
        try:
            self.db = Database(name)
        except ValidationError as exc:
            messagebox.showerror("Помилка", str(exc), parent=self)
            return

        self.current_file = None
        self.current_table_name = None
        self.is_dirty = False
        self.status_var.set(f"Створено нову базу даних '{self.db.name}'.")
        self._refresh_all()

    def _open_database(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        path = filedialog.askopenfilename(
            parent=self,
            title="Відкрити базу даних",
            filetypes=[("JSON бази даних", "*.json"), ("Усі файли", "*.*")],
        )
        if not path:
            return
        try:
            loaded = load_database(path)
        except (ValidationError, OSError) as exc:
            messagebox.showerror("Помилка завантаження", str(exc), parent=self)
            return

        self.db = loaded
        self.current_file = Path(path)
        self.current_table_name = None
        self.is_dirty = False
        self.status_var.set(f"Завантажено базу '{self.db.name}' з файлу {self.current_file.name}.")
        self._refresh_all()

    def _save_database(self) -> bool:
        if self.current_file is None:
            return self._save_database_as()
        try:
            save_database(self.db, self.current_file)
        except OSError as exc:
            messagebox.showerror("Помилка збереження", str(exc), parent=self)
            return False

        self.is_dirty = False
        self.status_var.set(f"Базу даних збережено у {self.current_file}.")
        self._refresh_all()
        return True

    def _save_database_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Зберегти базу даних як",
            defaultextension=".json",
            initialfile=f"{self.db.name}.json",
            filetypes=[("JSON бази даних", "*.json"), ("Усі файли", "*.*")],
        )
        if not path:
            return False
        self.current_file = Path(path)
        return self._save_database()

    # ---- Операції з таблицями ----

    def _on_table_select(self, _event: tk.Event[Any]) -> None:
        sel = self.tables_listbox.curselection()
        if not sel:
            return
        self.current_table_name = self.tables_listbox.get(sel[0])
        self._refresh_table_view()

    def _create_table(self) -> None:
        dialog = CreateTableDialog(self, self.db)
        self.wait_window(dialog)
        if dialog.created_table is not None:
            self.current_table_name = dialog.created_table.name
            self.is_dirty = True
            self.status_var.set(f"Створено таблицю '{dialog.created_table.name}'.")
            self._refresh_all()

    def _delete_table(self) -> None:
        if self.current_table_name is None:
            return
        confirm = messagebox.askyesno(
            "Підтвердження видалення",
            f"Ви дійсно бажаєте знищити таблицю '{self.current_table_name}' разом з усіма даними?",
            parent=self,
        )
        if not confirm:
            return

        deleted_name = self.current_table_name
        self.db.delete_table(deleted_name)
        self.current_table_name = None
        self.is_dirty = True
        self.status_var.set(f"Таблицю '{deleted_name}' видалено.")
        self._refresh_all()

    # ---- Операції з рядками ----

    def _get_selected_row_index(self) -> int | None:
        selected = self.data_tree.selection()
        if not selected:
            messagebox.showinfo("Увага", "Спочатку виберіть рядок у таблиці.", parent=self)
            return None
        return int(selected[0])

    def _add_row(self) -> None:
        if self.current_table_name is None:
            return
        table = self.db.get_table(self.current_table_name)
        dialog = RowEditorDialog(self, table, row_index=None)
        self.wait_window(dialog)
        if dialog.saved:
            self.is_dirty = True
            self.status_var.set(f"Додано рядок у таблицю '{table.name}'.")
            self._refresh_all()

    def _edit_row(self) -> None:
        if self.current_table_name is None:
            return
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return
        table = self.db.get_table(self.current_table_name)
        dialog = RowEditorDialog(self, table, row_index=row_idx)
        self.wait_window(dialog)
        if dialog.saved:
            self.is_dirty = True
            self.status_var.set(f"Оновлено рядок #{row_idx + 1} у таблиці '{table.name}'.")
            self._refresh_all()

    def _delete_row(self) -> None:
        if self.current_table_name is None:
            return
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return
        table = self.db.get_table(self.current_table_name)
        table.delete_row(row_idx)
        self.is_dirty = True
        self.status_var.set(f"Видалено рядок #{row_idx + 1}.")
        self._refresh_all()

    def _view_text_files(self) -> None:
        if self.current_table_name is None:
            return
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return
        table = self.db.get_table(self.current_table_name)
        TextFileViewerDialog(self, table, row_idx)

    def _remove_duplicates(self) -> None:
        if self.current_table_name is None:
            return
        table = self.db.get_table(self.current_table_name)
        removed = table.remove_duplicates()
        if removed > 0:
            self.is_dirty = True
            self._refresh_all()
            msg = f"Вилучено повторюваних рядків: {removed}."
        else:
            msg = "Повторюваних рядків не знайдено."
        self.status_var.set(msg)
        messagebox.showinfo("Вилучення дублікатів", msg, parent=self)

    def _on_exit(self) -> None:
        if self._confirm_discard_if_dirty():
            self.destroy()


if __name__ == "__main__":
    app = TableDBMSApp()
    app.mainloop()