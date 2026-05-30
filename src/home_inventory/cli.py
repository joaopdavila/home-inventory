"""Comandos do CLI `inv` (Typer)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

from . import engine
from .catalog import DEFAULT_CATALOG_PATH, Catalog, CatalogError, load_catalog
from .database import DEFAULT_DB_PATH, Database
from .formatter import (
    ListRow,
    dias,
    format_date_pt,
    qty_label,
    render_list,
    render_plain,
    stock_label,
)
from .models import ConsumableItem, MaintenanceItem

app = typer.Typer(
    add_completion=False,
    help="Rastreia estoque doméstico e gera lista de compras priorizada.",
)
console = Console()
err_console = Console(stderr=True)


# -- helpers --------------------------------------------------------------


def _catalog_path() -> Path:
    return DEFAULT_CATALOG_PATH


def _db_path() -> Path:
    return Path(DEFAULT_DB_PATH)


def _load() -> tuple[Catalog, Database]:
    """Carrega catálogo e banco, encerrando com mensagem clara em caso de erro."""
    try:
        catalog = load_catalog(_catalog_path())
    except CatalogError as exc:
        err_console.print(f"[bold red]Erro:[/] {exc}")
        raise typer.Exit(code=1)
    db = Database(_db_path())
    return catalog, db


def _get_item(catalog: Catalog, item_id: str):
    try:
        return catalog.get(item_id)
    except CatalogError as exc:
        err_console.print(f"[bold red]Erro:[/] {exc}")
        raise typer.Exit(code=1)


def _consumable_state(item: ConsumableItem, db: Database) -> dict:
    """Estado calculado de um consumível: estoque, taxa, dias, prioridade."""
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    days = engine.days_remaining(stock, rate)
    return {
        "stock": stock,
        "rate": rate,
        "days": days,
        "priority": engine.priority(days),
    }


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
    if overdue > 0:
        detail = f"vencido há {dias(overdue)}"
    else:
        detail = f"vence em {dias(-overdue)}"
    return ListRow(
        priority=prio,
        is_maintenance=True,
        name=item.name,
        qty_label="trocar",
        detail=detail,
    )


def _build_rows(catalog: Catalog, db: Database) -> list[ListRow]:
    rows: list[ListRow] = []
    for item in catalog:
        if isinstance(item, ConsumableItem):
            rows.append(_consumable_row(item, _consumable_state(item, db)))
        elif isinstance(item, MaintenanceItem):
            rows.append(_maintenance_row(item, db))
    return rows


# -- comandos -------------------------------------------------------------


@app.command("list")
def list_cmd(
    plain: bool = typer.Option(
        False, "--plain", help="Lista simples sem headers (para colar no WhatsApp)."
    ),
) -> None:
    """Gera a lista de compras priorizada."""
    catalog, db = _load()
    rows = _build_rows(catalog, db)
    if plain:
        out = render_plain(rows)
        if out:
            console.print(out)
    else:
        render_list(rows, date.today(), console)
    db.close()


@app.command("buy")
def buy_cmd(item_id: str, quantity: float) -> None:
    """Registra compra e atualiza o estoque imediatamente."""
    catalog, db = _load()
    item = _get_item(catalog, item_id)
    if not isinstance(item, ConsumableItem):
        err_console.print(
            f"[bold red]Erro:[/] '{item_id}' não é consumível; use 'inv done' para manutenção."
        )
        raise typer.Exit(code=1)

    db.add_event(item_id, "buy", quantity)
    stock = engine.current_stock(item, db)
    console.print(
        f"Registrado: +{_fmt_qty(quantity)} × {item.unit} de {item.name}. "
        f"Estoque atual: {stock_label(stock)}."
    )
    db.close()


@app.command("use")
def use_cmd(item_id: str, quantity: float) -> None:
    """Registra consumo, atualiza estoque e refina a taxa de consumo."""
    catalog, db = _load()
    item = _get_item(catalog, item_id)
    if not isinstance(item, ConsumableItem):
        err_console.print(
            f"[bold red]Erro:[/] '{item_id}' não é consumível."
        )
        raise typer.Exit(code=1)

    db.add_event(item_id, "use", quantity)
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    days = engine.days_remaining(stock, rate)

    msg = (
        f"Registrado: -{_fmt_qty(quantity)} {item.unit} de {item.name}. "
        f"Estoque atual: {stock_label(stock)}."
    )
    if engine.priority(days) == engine.URGENTE:
        msg += " ⚠ URGENTE"
    console.print(msg)
    db.close()


@app.command("done")
def done_cmd(item_id: str) -> None:
    """Registra manutenção feita e reseta o contador do intervalo."""
    catalog, db = _load()
    item = _get_item(catalog, item_id)
    if not isinstance(item, MaintenanceItem):
        err_console.print(
            f"[bold red]Erro:[/] '{item_id}' não é item de manutenção."
        )
        raise typer.Exit(code=1)

    today = date.today()
    db.add_maintenance(item_id, today.isoformat())
    next_due = today + timedelta(days=item.interval_days)
    console.print(
        f"Registrado: {item.name} — troca em {today.isoformat()}. "
        f"Próxima em {next_due.isoformat()}."
    )
    db.close()


@app.command("stock")
def stock_cmd() -> None:
    """Modo interativo de inventário dos consumíveis."""
    catalog, db = _load()
    console.print(f"Inventário rápido — {format_date_pt(date.today())}")
    console.print("(enter = confirmar, número = corrigir)\n")

    corrections = 0
    for item in catalog.consumables():
        calc = engine.current_stock(item, db)
        prompt = f"{item.name:<18}calculado: {stock_label(calc)}  →"
        try:
            answer = typer.prompt(
                prompt, default="", show_default=False, prompt_suffix=" "
            ).strip()
        except (EOFError, typer.Abort):
            answer = ""
        if answer:
            try:
                corrected = float(answer.replace(",", "."))
            except ValueError:
                err_console.print(f"  valor inválido ignorado: {answer!r}")
                continue
            db.add_event(item.id, "stock_correction", corrected, note="inv stock")
            corrections += 1

    plural = "correção registrada" if corrections == 1 else "correções registradas"
    console.print(f"\nInventário salvo. {corrections} {plural}.")
    db.close()


@app.command("status")
def status_cmd(item_id: str) -> None:
    """Exibe histórico e projeção de um item específico."""
    catalog, db = _load()
    item = _get_item(catalog, item_id)

    if isinstance(item, ConsumableItem):
        _status_consumable(item, db)
    elif isinstance(item, MaintenanceItem):
        _status_maintenance(item, db)
    db.close()


def _status_consumable(item: ConsumableItem, db: Database) -> None:
    stock = engine.current_stock(item, db)
    rate = engine.effective_rate(item.id, db, item.consumption_rate)
    hist = engine.history_days(item.id, db)
    days = engine.days_remaining(stock, rate)
    buy = engine.quantity_to_buy(stock, item.stock_target)

    base = (
        f"baseado em {hist} dias de histórico"
        if hist
        else "estimativa do catálogo"
    )
    console.print(item.name)
    console.print(f"  Estoque atual:    {qty_label(int(stock), item.unit)}")
    console.print(f"  Consumo médio:    {rate:.2f}/dia ({base})")
    if math.isinf(days):
        console.print("  Acaba em:         estável (sem consumo registrado)")
    else:
        eta = date.today() + timedelta(days=int(round(days)))
        console.print(
            f"  Acaba em:         ~{int(round(days))} dias ({eta.isoformat()})"
        )
    console.print(f"  Stock target:     {stock_label(item.stock_target)}")
    console.print(f"  Comprar:          {stock_label(buy)}")


def _status_maintenance(item: MaintenanceItem, db: Database) -> None:
    last = db.last_maintenance(item.id)
    last_done = date.fromisoformat(last) if last else item.last_done
    overdue = engine.days_overdue(last_done, item.interval_days)
    next_due = last_done + timedelta(days=item.interval_days)
    if overdue > 0:
        situacao = f"vencido há {dias(overdue)}"
    else:
        situacao = f"vence em {dias(-overdue)}"
    console.print(item.name)
    console.print(f"  Última troca:     {last_done.isoformat()}")
    console.print(f"  Intervalo:        {item.interval_days} dias")
    console.print(f"  Próxima troca:    {next_due.isoformat()} ({situacao})")


def _fmt_qty(quantity: float) -> str:
    """Mostra inteiros sem casa decimal (2.0 -> '2'), decimais como estão."""
    return str(int(quantity)) if float(quantity).is_integer() else str(quantity)


if __name__ == "__main__":
    app()
