from __future__ import annotations

from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core import (
    Column,
    Database,
    FieldType,
    ValidationError,
    load_database,
    save_database,
)

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
SAVED_DBS_DIR = BASE_DIR / "saved_dbs"
SAVED_DBS_DIR.mkdir(exist_ok=True)


class AppState:
    def __init__(self) -> None:
        self.db: Database = Database("WebDatabase")
        self.current_file: str | None = None


state = AppState()

app = FastAPI(
    title="Таблична СУБД — REST API",
    description="Веб-версія системи управління табличними БД (Варіант 1 / 5)",
    version="1.0.0",
)


@app.exception_handler(ValidationError)
async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---- Pydantic-схеми запитів ----

class DatabaseNameRequest(BaseModel):
    name: str


class FileActionRequest(BaseModel):
    filename: str


class ImportDatabaseRequest(BaseModel):
    data: dict[str, Any]


class ColumnSchema(BaseModel):
    name: str
    field_type: str


class CreateTableRequest(BaseModel):
    name: str
    columns: list[ColumnSchema]


class RowPayload(BaseModel):
    row: dict[str, Any]


def _list_saved_files() -> list[str]:
    return sorted(p.name for p in SAVED_DBS_DIR.glob("*.json") if p.is_file())


def _safe_db_path(filename: str) -> Path:
    clean = Path(filename.strip()).name
    if not clean:
        raise ValidationError("Назва файлу не може бути порожньою.")
    if not clean.lower().endswith(".json"):
        clean += ".json"
    return SAVED_DBS_DIR / clean


# ---- Маршрути веб-інтерфейсу та REST API ----

@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    return {
        "db_name": state.db.name,
        "current_file": state.current_file,
        "field_types": FieldType.labels(),
        "tables": [
            {
                "name": t.name,
                "columns": [c.to_dict() for c in t.columns],
                "row_count": len(t.rows),
            }
            for t in state.db.tables.values()
        ],
        "saved_files": _list_saved_files(),
    }


@app.post("/api/database/new")
def create_new_database(payload: DatabaseNameRequest) -> dict[str, Any]:
    state.db = Database(payload.name)
    state.current_file = None
    return {"message": f"Створено базу даних '{state.db.name}'.", "db_name": state.db.name}


@app.post("/api/database/save")
def save_db_to_disk(payload: FileActionRequest) -> dict[str, Any]:
    path = _safe_db_path(payload.filename)
    save_database(state.db, path)
    state.current_file = path.name
    return {"message": f"Базу даних збережено у '{path.name}'.", "filename": path.name}


@app.post("/api/database/load")
def load_db_from_disk(payload: FileActionRequest) -> dict[str, Any]:
    path = _safe_db_path(payload.filename)
    state.db = load_database(path)
    state.current_file = path.name
    return {"message": f"Завантажено базу '{state.db.name}' з '{path.name}'.", "db_name": state.db.name}


@app.get("/api/database/export")
def export_db_json() -> Response:
    import json

    content = json.dumps(state.db.to_dict(), ensure_ascii=False, indent=2)
    filename = f"{state.db.name}.json"
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/database/import")
def import_db_json(payload: ImportDatabaseRequest) -> dict[str, Any]:
    state.db = Database.from_dict(payload.data)
    state.current_file = None
    return {"message": f"Імпортовано базу даних '{state.db.name}'.", "db_name": state.db.name}


@app.get("/api/tables/{table_name}")
def get_table(table_name: str) -> dict[str, Any]:
    table = state.db.get_table(table_name)
    return table.to_dict()


@app.post("/api/tables")
def create_table(payload: CreateTableRequest) -> dict[str, Any]:
    columns = [Column(name=c.name, field_type=FieldType(c.field_type)) for c in payload.columns]
    table = state.db.create_table(payload.name, columns)
    return table.to_dict()


@app.delete("/api/tables/{table_name}")
def delete_table(table_name: str) -> dict[str, Any]:
    state.db.delete_table(table_name)
    return {"message": f"Таблицю '{table_name}' видалено."}


@app.post("/api/tables/{table_name}/rows")
def add_row(table_name: str, payload: RowPayload) -> dict[str, Any]:
    table = state.db.get_table(table_name)
    created = table.add_row(payload.row)
    return {"row": created, "total_rows": len(table.rows)}


@app.put("/api/tables/{table_name}/rows/{row_index}")
def edit_row(table_name: str, row_index: int, payload: RowPayload) -> dict[str, Any]:
    table = state.db.get_table(table_name)
    updated = table.edit_row(row_index, payload.row)
    return {"row": updated}


@app.delete("/api/tables/{table_name}/rows/{row_index}")
def delete_row(table_name: str, row_index: int) -> dict[str, Any]:
    table = state.db.get_table(table_name)
    table.delete_row(row_index)
    return {"message": f"Рядок #{row_index + 1} видалено."}


@app.post("/api/tables/{table_name}/deduplicate")
def remove_duplicates(table_name: str) -> dict[str, Any]:
    table = state.db.get_table(table_name)
    removed = table.remove_duplicates()
    return {"removed": removed, "table": table.to_dict()}


if __name__ == "__main__":
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True)