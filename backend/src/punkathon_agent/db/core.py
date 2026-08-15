from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine

from punkathon_agent.models.db import DEFAULT_USER_GOAL, MovimentoBancario, PunkUser, Utente
from punkathon_agent.services.classification import split_legacy_category_label

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_DIR = PROJECT_ROOT / "db"
DB_PATH = DB_DIR / "movimenti_bancari.sqlite3"
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH}"
DATABASE_URL_ENV_VAR = "DATABASE_URL"
DATABASE_URL = os.getenv(DATABASE_URL_ENV_VAR, DEFAULT_DATABASE_URL)


def _is_sqlite_database(database_url: str = DATABASE_URL) -> bool:
    return database_url.startswith("sqlite")


engine_kwargs: dict[str, Any] = {
    "echo": False,
    "pool_pre_ping": True,
}
if _is_sqlite_database():
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)


def _sqlite_sidecar_paths(db_path: Path) -> tuple[Path, ...]:
    return (
        db_path.with_name(f"{db_path.name}-shm"),
        db_path.with_name(f"{db_path.name}-wal"),
    )


def _sqlite_table_exists(connection: Any, table_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    ).scalar()
    return bool(result)


def _sqlite_column_names(connection: Any, table_name: str) -> set[str]:
    if not _sqlite_table_exists(connection, table_name):
        return set()
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    return {str(row["name"]) for row in rows}


def _ensure_sqlite_index(connection: Any, index_name: str, create_sql: str) -> None:
    existing = connection.execute(
        text(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'index' AND name = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar()
    if existing:
        return
    connection.execute(text(create_sql))


def _rebuild_movimenti_bancari_table(connection: Any) -> None:
    if not _sqlite_table_exists(connection, "movimenti_bancari"):
        return

    column_names = _sqlite_column_names(connection, "movimenti_bancari")
    if {"id", "user_id"}.issubset(column_names):
        return

    connection.execute(text("ALTER TABLE movimenti_bancari RENAME TO movimenti_bancari_legacy"))
    connection.execute(
        text(
            """
            CREATE TABLE movimenti_bancari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES punk_users (id),
                data DATE NOT NULL,
                descrizione TEXT NOT NULL,
                importo REAL NOT NULL,
                note TEXT,
                categoria TEXT,
                macrocategoria TEXT
            )
            """
        )
    )

    legacy_select_parts = [
        "user_id" if "user_id" in column_names else "NULL AS user_id",
        "data",
        "descrizione",
        "importo",
        "note" if "note" in column_names else "NULL AS note",
        "categoria" if "categoria" in column_names else "NULL AS categoria",
        "macrocategoria" if "macrocategoria" in column_names else "NULL AS macrocategoria",
    ]
    connection.execute(
        text(
            f"""
            INSERT INTO movimenti_bancari (user_id, data, descrizione, importo, note, categoria, macrocategoria)
            SELECT {", ".join(legacy_select_parts)}
            FROM movimenti_bancari_legacy
            """
        )
    )
    connection.execute(text("DROP TABLE movimenti_bancari_legacy"))


def _rebuild_utente_table(connection: Any) -> None:
    if not _sqlite_table_exists(connection, "utente"):
        return

    column_names = _sqlite_column_names(connection, "utente")
    if {"id", "user_id"}.issubset(column_names):
        return

    connection.execute(text("ALTER TABLE utente RENAME TO utente_legacy"))
    connection.execute(
        text(
            """
            CREATE TABLE utente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE REFERENCES punk_users (id),
                stipendio_mensile REAL,
                spese_fisse_essenziali_mensili REAL,
                disponibile_mensile REAL,
                disponibile_settimanale REAL,
                obiettivo TEXT,
                spese_irrinunciabili TEXT,
                risparmio REAL
            )
            """
        )
    )

    legacy_select_parts = [
        "user_id" if "user_id" in column_names else "NULL AS user_id",
        "stipendio_mensile" if "stipendio_mensile" in column_names else "NULL AS stipendio_mensile",
        (
            "spese_fisse_essenziali_mensili"
            if "spese_fisse_essenziali_mensili" in column_names
            else "NULL AS spese_fisse_essenziali_mensili"
        ),
        "disponibile_mensile" if "disponibile_mensile" in column_names else "NULL AS disponibile_mensile",
        "disponibile_settimanale" if "disponibile_settimanale" in column_names else "NULL AS disponibile_settimanale",
        "obiettivo" if "obiettivo" in column_names else "NULL AS obiettivo",
        "spese_irrinunciabili" if "spese_irrinunciabili" in column_names else "NULL AS spese_irrinunciabili",
        "risparmio" if "risparmio" in column_names else "NULL AS risparmio",
    ]
    connection.execute(
        text(
            f"""
            INSERT INTO utente (
                user_id,
                stipendio_mensile,
                spese_fisse_essenziali_mensili,
                disponibile_mensile,
                disponibile_settimanale,
                obiettivo,
                spese_irrinunciabili,
                risparmio
            )
            SELECT {", ".join(legacy_select_parts)}
            FROM utente_legacy
            """
        )
    )
    connection.execute(text("DROP TABLE utente_legacy"))


def _run_schema_migrations() -> None:
    with engine.begin() as connection:
        _rebuild_utente_table(connection)
        _rebuild_movimenti_bancari_table(connection)

        _ensure_sqlite_index(
            connection,
            "idx_movimenti_bancari_user_id",
            "CREATE INDEX idx_movimenti_bancari_user_id ON movimenti_bancari (user_id)",
        )
        _ensure_sqlite_index(
            connection,
            "idx_movimenti_bancari_data",
            "CREATE INDEX idx_movimenti_bancari_data ON movimenti_bancari (data)",
        )
        _ensure_sqlite_index(
            connection,
            "idx_movimenti_bancari_descrizione",
            "CREATE INDEX idx_movimenti_bancari_descrizione ON movimenti_bancari (descrizione)",
        )
        _ensure_sqlite_index(
            connection,
            "idx_movimenti_bancari_categoria",
            "CREATE INDEX idx_movimenti_bancari_categoria ON movimenti_bancari (categoria)",
        )
        _ensure_sqlite_index(
            connection,
            "idx_movimenti_bancari_macrocategoria",
            "CREATE INDEX idx_movimenti_bancari_macrocategoria ON movimenti_bancari (macrocategoria)",
        )
        _ensure_sqlite_index(
            connection,
            "idx_utente_user_id",
            "CREATE UNIQUE INDEX idx_utente_user_id ON utente (user_id)",
        )


def _run_data_migrations() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE utente
                SET obiettivo = :obiettivo
                WHERE obiettivo IS NULL OR TRIM(obiettivo) = ''
                """
            ),
            {"obiettivo": DEFAULT_USER_GOAL},
        )

        rows = connection.execute(
            text(
                """
                SELECT id, descrizione, categoria, note
                FROM movimenti_bancari
                WHERE categoria IN ('Ristoranti | Bar', 'Spese Mediche e Farmacia')
                """
            )
        ).mappings().all()

        for row in rows:
            updated_category = split_legacy_category_label(
                row["categoria"],
                descrizione=row["descrizione"],
                note=row["note"],
            )
            if updated_category is None or updated_category == row["categoria"]:
                continue

            connection.execute(
                text(
                    """
                    UPDATE movimenti_bancari
                    SET categoria = :categoria
                    WHERE id = :movement_id
                    """
                ),
                {
                    "categoria": updated_category,
                    "movement_id": row["id"],
                },
            )


def create_database() -> Path | str:
    if _is_sqlite_database():
        DB_DIR.mkdir(parents=True, exist_ok=True)

    SQLModel.metadata.create_all(engine)
    if _is_sqlite_database():
        _run_schema_migrations()
    SQLModel.metadata.create_all(engine)
    _run_data_migrations()
    return DB_PATH if _is_sqlite_database() else DATABASE_URL


def drop_application_tables() -> None:
    SQLModel.metadata.drop_all(
        engine,
        tables=[
            MovimentoBancario.__table__,
            Utente.__table__,
            PunkUser.__table__,
        ],
    )


def delete_database() -> list[Path]:
    if not _is_sqlite_database():
        raise RuntimeError("delete_database e' supportato solo con il database SQLite locale.")

    engine.dispose()

    removed_paths: list[Path] = []
    for path in (DB_PATH, *_sqlite_sidecar_paths(DB_PATH)):
        if not path.exists():
            continue
        path.unlink()
        removed_paths.append(path)

    return removed_paths


def rebuild_database() -> Path | str:
    if not _is_sqlite_database():
        raise RuntimeError("rebuild_database e' supportato solo con il database SQLite locale.")

    delete_database()
    return create_database()


def recreate_database() -> Path | str:
    if _is_sqlite_database():
        return rebuild_database()

    drop_application_tables()
    return create_database()


def get_session() -> Session:
    create_database()
    return Session(engine, expire_on_commit=False)


def main() -> None:
    print(create_database())


__all__ = [
    "DATABASE_URL",
    "DATABASE_URL_ENV_VAR",
    "DB_DIR",
    "DB_PATH",
    "DEFAULT_DATABASE_URL",
    "MovimentoBancario",
    "PunkUser",
    "Utente",
    "create_database",
    "delete_database",
    "drop_application_tables",
    "engine",
    "get_session",
    "main",
    "recreate_database",
    "rebuild_database",
]
