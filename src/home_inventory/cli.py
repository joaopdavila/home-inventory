"""Comandos do CLI `inv` (Typer)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from . import engine, service
from .catalog import DEFAULT_CATALOG_PATH, Catalog, CatalogError, load_catalog
from .database import DEFAULT_DB_PATH, Database
from .formatter import format_date_pt, render_list, stock_label

app = typer.Typer(
    add_completion=False,
    help="Rastreia estoque doméstico e gera lista de compras priorizada.",
)
console = Console()
err_console = Console(stderr=True)


# -- helpers --------------------------------------------------------------


def _load() -> tuple[Catalog, Database]:
    """Carrega catálogo e banco, encerrando com mensagem clara em caso de erro."""
    try:
        catalog = load_catalog(DEFAULT_CATALOG_PATH)
    except CatalogError as exc:
        err_console.print(f"[bold red]Erro:[/] {exc}")
        raise typer.Exit(code=1)
    db = Database(Path(DEFAULT_DB_PATH))
    return catalog, db


def _fail(message: str) -> None:
    err_console.print(f"[bold red]Erro:[/] {message}")
    raise typer.Exit(code=1)


# -- comandos -------------------------------------------------------------


@app.command("list")
def list_cmd(
    plain: bool = typer.Option(
        False, "--plain", help="Lista simples sem headers (para colar no WhatsApp)."
    ),
) -> None:
    """Gera a lista de compras priorizada."""
    catalog, db = _load()
    rows = service.build_rows(catalog, db)
    if plain:
        out = service.shopping_list_plain(catalog, db)
        if out:
            console.print(out)
    else:
        render_list(rows, date.today(), console)
    db.close()


@app.command("buy")
def buy_cmd(item_id: str, quantity: float) -> None:
    """Registra compra e atualiza o estoque imediatamente."""
    catalog, db = _load()
    try:
        result = service.register_buy(catalog, db, item_id, quantity)
    except (CatalogError, service.ServiceError) as exc:
        _fail(str(exc))
    console.print(result.message)
    db.close()


@app.command("use")
def use_cmd(item_id: str, quantity: float) -> None:
    """Registra consumo, atualiza estoque e refina a taxa de consumo."""
    catalog, db = _load()
    try:
        result = service.register_use(catalog, db, item_id, quantity)
    except (CatalogError, service.ServiceError) as exc:
        _fail(str(exc))
    console.print(result.message)
    db.close()


@app.command("done")
def done_cmd(item_id: str) -> None:
    """Registra manutenção feita e reseta o contador do intervalo."""
    catalog, db = _load()
    try:
        result = service.register_done(catalog, db, item_id)
    except (CatalogError, service.ServiceError) as exc:
        _fail(str(exc))
    console.print(result.message)
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
            service.record_stock_correction(db, item.id, corrected, note="inv stock")
            corrections += 1

    plural = "correção registrada" if corrections == 1 else "correções registradas"
    console.print(f"\nInventário salvo. {corrections} {plural}.")
    db.close()


@app.command("status")
def status_cmd(item_id: str) -> None:
    """Exibe histórico e projeção de um item específico."""
    catalog, db = _load()
    try:
        lines = service.status_lines(catalog, db, item_id)
    except CatalogError as exc:
        _fail(str(exc))
    for line in lines:
        console.print(line)
    db.close()


if __name__ == "__main__":
    app()
