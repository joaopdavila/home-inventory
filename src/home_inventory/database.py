"""Wrapper fino sobre SQLite (sem ORM)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Event

DEFAULT_DB_PATH = Path("data/inventory.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,  -- 'buy' | 'use' | 'stock_correction'
    quantity    REAL,              -- unidades (NULL para maintenance)
    note        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS maintenance_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    TEXT NOT NULL,
    done_at    TEXT NOT NULL      -- ISO 8601 date
);
"""


class Database:
    """Conexão SQLite + operações de leitura/escrita de eventos e manutenção.

    O banco é criado automaticamente no primeiro uso (cria as tabelas se
    ainda não existirem). Use `path=":memory:"` em testes.
    """

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- eventos -----------------------------------------------------------

    def add_event(
        self,
        item_id: str,
        event_type: str,
        quantity: float | None = None,
        note: str | None = None,
    ) -> int:
        """Insere um evento e retorna o id gerado."""
        cur = self.conn.execute(
            "INSERT INTO events (item_id, event_type, quantity, note) "
            "VALUES (?, ?, ?, ?)",
            (item_id, event_type, quantity, note),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def events_for(self, item_id: str, since: str | None = None) -> list[Event]:
        """Eventos de um item, em ordem cronológica.

        `since` opcional filtra `created_at >= since` (string ISO comparável).
        """
        sql = "SELECT * FROM events WHERE item_id = ?"
        params: list[object] = [item_id]
        if since is not None:
            sql += " AND created_at >= ?"
            params.append(since)
        sql += " ORDER BY created_at ASC, id ASC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    # -- manutenção --------------------------------------------------------

    def add_maintenance(self, item_id: str, done_at: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO maintenance_log (item_id, done_at) VALUES (?, ?)",
            (item_id, done_at),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def last_maintenance(self, item_id: str) -> str | None:
        """Data (ISO) da última manutenção registrada, ou None."""
        row = self.conn.execute(
            "SELECT done_at FROM maintenance_log WHERE item_id = ? "
            "ORDER BY done_at DESC, id DESC LIMIT 1",
            (item_id,),
        ).fetchone()
        return row["done_at"] if row else None

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            item_id=row["item_id"],
            event_type=row["event_type"],
            quantity=row["quantity"],
            note=row["note"],
            created_at=row["created_at"],
        )
