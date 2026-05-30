"""Dataclasses do domínio: itens do catálogo e eventos do banco."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

CONSUMABLE = "consumable"
MAINTENANCE = "maintenance"


@dataclass
class Item:
    """Base comum a todos os itens do catálogo."""

    id: str
    name: str
    type: str


@dataclass
class ConsumableItem(Item):
    """Item consumível — reposição baseada em taxa de consumo medida."""

    unit: str
    stock_target: int
    initial_stock: float
    consumption_rate: float

    def __post_init__(self) -> None:
        self.type = CONSUMABLE


@dataclass
class MaintenanceItem(Item):
    """Item de manutenção — reposição baseada em intervalo fixo (dias)."""

    interval_days: int
    last_done: date

    def __post_init__(self) -> None:
        self.type = MAINTENANCE


@dataclass
class Event:
    """Linha da tabela `events`."""

    id: int | None
    item_id: str
    event_type: str  # 'buy' | 'use' | 'stock_correction'
    quantity: float | None
    note: str | None
    created_at: str
