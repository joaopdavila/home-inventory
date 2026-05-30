"""Camada de serviço: ações de inventário compartilhadas entre CLI e bot.

Cada função recebe um `Catalog` e um `Database` já abertos, executa a ação e
devolve o texto de resposta (ou dados estruturados). Assim o CLI e o bot do
Telegram produzem exatamente as mesmas mensagens e a mesma lógica.

Erros de domínio (item inexistente, tipo errado) são levantados como
`CatalogError` / `ServiceError` para o chamador formatar como preferir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from . import engine
from .catalog import Catalog
from .database import Database
from .formatter import ListRow, dias, qty_label, render_plain, stock_label
from .models import ConsumableItem, MaintenanceItem


class ServiceError(Exception):
    """Erro de uso de uma ação (ex.: tipo de item incompatível)."""


@dataclass
class ActionResult:
    """Resultado de uma ação que altera estoque/manutenção."""

    message: str
    urgent: bool = False


def fmt_qty(quantity: float) -> str:
    """Inteiros sem casa decimal (2.0 -> '2'); decimais como estão."""
    return str(int(quantity)) if float(quantity).is_integer() else str(quantity)


# -- montagem da lista ----------------------------------------------------


def _consumable_state(item: ConsumableItem, db: Database) -> dict:
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    days = engine.days_remaining(stock, rate)
    return {"stock": stock, "rate": rate, "days": days, "priority": engine.priority(days)}


def _consumable_row(item: ConsumableItem, st: dict) -> ListRow:
    buy = engine.quantity_to_buy(st["stock"], item.stock_target)
    days = st["days"]
    detail = "estável" if math.isinf(days) else f"acaba em {dias(int(round(days)))}"
    return ListRow(
        priority=st["priority"],
        is_maintenance=False,
        name=item.name,
        qty_label=qty_label(buy, item.unit),
        detail=detail,
    )


def _maintenance_row(item: MaintenanceItem, db: Database) -> ListRow:
    last = db.last_maintenance(item.id)
    last_done = date.fromisoformat(last) if last else item.last_done
    overdue = engine.days_overdue(last_done, item.interval_days)
    prio = engine.maintenance_priority(overdue)
    detail = f"vencido há {dias(overdue)}" if overdue > 0 else f"vence em {dias(-overdue)}"
    return ListRow(
        priority=prio,
        is_maintenance=True,
        name=item.name,
        qty_label="trocar",
        detail=detail,
    )


def build_rows(catalog: Catalog, db: Database) -> list[ListRow]:
    """Linhas classificadas da lista de compras (consumíveis + manutenção)."""
    rows: list[ListRow] = []
    for item in catalog:
        if isinstance(item, ConsumableItem):
            rows.append(_consumable_row(item, _consumable_state(item, db)))
        elif isinstance(item, MaintenanceItem):
            rows.append(_maintenance_row(item, db))
    return rows


def shopping_list_plain(catalog: Catalog, db: Database) -> str:
    """Lista enxuta (formato WhatsApp/Telegram), só itens acionáveis."""
    return render_plain(build_rows(catalog, db))


# -- ações ----------------------------------------------------------------


def _require_consumable(catalog: Catalog, item_id: str) -> ConsumableItem:
    item = catalog.get(item_id)  # CatalogError se não existir
    if not isinstance(item, ConsumableItem):
        raise ServiceError(f"'{item_id}' não é um item consumível.")
    return item


def _require_maintenance(catalog: Catalog, item_id: str) -> MaintenanceItem:
    item = catalog.get(item_id)
    if not isinstance(item, MaintenanceItem):
        raise ServiceError(f"'{item_id}' não é um item de manutenção.")
    return item


def register_buy(
    catalog: Catalog, db: Database, item_id: str, quantity: float
) -> ActionResult:
    item = _require_consumable(catalog, item_id)
    db.add_event(item_id, "buy", quantity)
    stock = engine.current_stock(item, db)
    return ActionResult(
        f"Registrado: +{fmt_qty(quantity)} × {item.unit} de {item.name}. "
        f"Estoque atual: {stock_label(stock)}."
    )


def register_use(
    catalog: Catalog, db: Database, item_id: str, quantity: float
) -> ActionResult:
    item = _require_consumable(catalog, item_id)
    db.add_event(item_id, "use", quantity)
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    days = engine.days_remaining(stock, rate)
    urgent = engine.priority(days) == engine.URGENTE
    msg = (
        f"Registrado: -{fmt_qty(quantity)} {item.unit} de {item.name}. "
        f"Estoque atual: {stock_label(stock)}."
    )
    if urgent:
        msg += " ⚠ URGENTE"
    return ActionResult(msg, urgent=urgent)


def register_done(catalog: Catalog, db: Database, item_id: str) -> ActionResult:
    item = _require_maintenance(catalog, item_id)
    today = date.today()
    db.add_maintenance(item_id, today.isoformat())
    next_due = today + timedelta(days=item.interval_days)
    return ActionResult(
        f"Registrado: {item.name} — troca em {today.isoformat()}. "
        f"Próxima em {next_due.isoformat()}."
    )


def record_stock_correction(db: Database, item_id: str, value: float, note: str) -> None:
    db.add_event(item_id, "stock_correction", value, note=note)


def status_lines(catalog: Catalog, db: Database, item_id: str) -> list[str]:
    """Linhas do status de um item (consumível ou manutenção)."""
    item = catalog.get(item_id)
    if isinstance(item, ConsumableItem):
        return _status_consumable_lines(item, db)
    return _status_maintenance_lines(item, db)  # type: ignore[arg-type]


def _status_consumable_lines(item: ConsumableItem, db: Database) -> list[str]:
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    hist = engine.history_days(item.id, db)
    days = engine.days_remaining(stock, rate)
    buy = engine.quantity_to_buy(stock, item.stock_target)
    base = f"baseado em {hist} dias de histórico" if hist else "estimativa do catálogo"

    lines = [
        item.name,
        f"  Estoque atual:    {qty_label(int(stock), item.unit)}",
        f"  Consumo médio:    {rate:.2f}/dia ({base})",
    ]
    if math.isinf(days):
        lines.append("  Acaba em:         estável (sem consumo registrado)")
    else:
        eta = date.today() + timedelta(days=int(round(days)))
        lines.append(f"  Acaba em:         ~{int(round(days))} dias ({eta.isoformat()})")
    lines.append(f"  Stock target:     {stock_label(item.stock_target)}")
    lines.append(f"  Comprar:          {stock_label(buy)}")
    return lines


def _status_maintenance_lines(item: MaintenanceItem, db: Database) -> list[str]:
    last = db.last_maintenance(item.id)
    last_done = date.fromisoformat(last) if last else item.last_done
    overdue = engine.days_overdue(last_done, item.interval_days)
    next_due = last_done + timedelta(days=item.interval_days)
    situacao = f"vencido há {dias(overdue)}" if overdue > 0 else f"vence em {dias(-overdue)}"
    return [
        item.name,
        f"  Última troca:     {last_done.isoformat()}",
        f"  Intervalo:        {item.interval_days} dias",
        f"  Próxima troca:    {next_due.isoformat()} ({situacao})",
    ]
