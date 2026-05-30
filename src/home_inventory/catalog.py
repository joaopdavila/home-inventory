"""Leitura e validação de `data/items.yaml`.

O catálogo é editado manualmente pelo usuário no setup e nunca é alterado
pelo CLI em runtime.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from .models import CONSUMABLE, MAINTENANCE, ConsumableItem, Item, MaintenanceItem

DEFAULT_CATALOG_PATH = Path("data/items.yaml")


class CatalogError(Exception):
    """Erro de leitura/validação do catálogo."""


class Catalog:
    """Coleção de itens carregada do YAML, com lookup por id."""

    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self._by_id = {item.id: item for item in items}

    def get(self, item_id: str) -> Item:
        """Retorna o item pelo id ou levanta erro claro se não existir."""
        try:
            return self._by_id[item_id]
        except KeyError:
            raise CatalogError(
                f"Item '{item_id}' não encontrado em items.yaml"
            ) from None

    def consumables(self) -> list[ConsumableItem]:
        return [i for i in self.items if isinstance(i, ConsumableItem)]

    def maintenance(self) -> list[MaintenanceItem]:
        return [i for i in self.items if isinstance(i, MaintenanceItem)]

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> Catalog:
    """Carrega e valida o catálogo a partir do YAML."""
    path = Path(path)
    if not path.exists():
        raise CatalogError(
            f"Catálogo não encontrado em '{path}'. "
            "Crie o arquivo data/items.yaml com a lista de itens antes de usar o CLI."
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CatalogError(f"YAML inválido em '{path}': {exc}") from exc

    entries = raw.get("items")
    if not isinstance(entries, list):
        raise CatalogError(
            f"'{path}' deve conter uma chave 'items' com uma lista de itens."
        )

    items = [_parse_item(entry) for entry in entries]
    _check_unique_ids(items)
    return Catalog(items)


def _parse_item(entry: dict) -> Item:
    if not isinstance(entry, dict):
        raise CatalogError(f"Item inválido (esperado mapeamento): {entry!r}")

    item_id = entry.get("id")
    name = entry.get("name")
    item_type = entry.get("type")

    if not item_id:
        raise CatalogError(f"Item sem 'id': {entry!r}")
    if not name:
        raise CatalogError(f"Item '{item_id}' sem 'name'.")

    if item_type == CONSUMABLE:
        return _parse_consumable(item_id, name, entry)
    if item_type == MAINTENANCE:
        return _parse_maintenance(item_id, name, entry)
    raise CatalogError(
        f"Item '{item_id}' tem type inválido: {item_type!r} "
        f"(esperado '{CONSUMABLE}' ou '{MAINTENANCE}')."
    )


def _parse_consumable(item_id: str, name: str, entry: dict) -> ConsumableItem:
    required = ("unit", "stock_target", "initial_stock", "consumption_rate")
    _require_fields(item_id, entry, required)
    return ConsumableItem(
        id=item_id,
        name=name,
        type=CONSUMABLE,
        unit=str(entry["unit"]),
        stock_target=int(entry["stock_target"]),
        initial_stock=float(entry["initial_stock"]),
        consumption_rate=float(entry["consumption_rate"]),
    )


def _parse_maintenance(item_id: str, name: str, entry: dict) -> MaintenanceItem:
    _require_fields(item_id, entry, ("interval_days", "last_done"))
    return MaintenanceItem(
        id=item_id,
        name=name,
        type=MAINTENANCE,
        interval_days=int(entry["interval_days"]),
        last_done=_parse_date(item_id, entry["last_done"]),
    )


def _require_fields(item_id: str, entry: dict, fields: tuple[str, ...]) -> None:
    missing = [f for f in fields if entry.get(f) is None]
    if missing:
        raise CatalogError(
            f"Item '{item_id}' está sem os campos obrigatórios: {', '.join(missing)}."
        )


def _parse_date(item_id: str, value: object) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise CatalogError(
            f"Item '{item_id}' tem last_done inválido: {value!r} "
            "(esperado data ISO 8601, ex.: 2026-02-15)."
        ) from exc


def _check_unique_ids(items: list[Item]) -> None:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise CatalogError(f"Id de item duplicado no catálogo: '{item.id}'.")
        seen.add(item.id)
