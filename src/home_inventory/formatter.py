"""Formatação do output da lista de compras.

Usa `rich` para o modo padrão (com seções e cores) e texto puro no modo
`--plain` (uma linha por item, fácil de colar no WhatsApp).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from rich.console import Console
from rich.text import Text

from .engine import OK, SEMANA, URGENTE

_MESES_PT = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]


def format_date_pt(d: date) -> str:
    """Ex.: date(2026, 5, 30) -> '30 mai 2026'."""
    return f"{d.day} {_MESES_PT[d.month - 1]} {d.year}"


@dataclass
class ListRow:
    """Uma linha da lista de compras, já classificada e descrita."""

    priority: str           # URGENTE | SEMANA QUE VEM | OK
    is_maintenance: bool
    name: str
    qty_label: str          # ex.: "2 × 500ml", "1 pacote", "trocar"
    detail: str             # ex.: "acaba em 2 dias", "vencido há 5 dias"


# Cabeçalhos das seções da lista padrão (ordem de exibição).
_SECTIONS = [
    (URGENTE, "URGENTE  (acaba em ≤ 3 dias ou manutenção vencida)", False),
    (SEMANA, "SEMANA QUE VEM  (acaba em 4–10 dias ou manutenção vence em ≤ 7 dias)", False),
    ("MANUTENÇÃO", "MANUTENÇÃO  (vencida ou vence em breve)", True),
    (OK, "OK  (sem ação necessária)", False),
]

_STYLES = {
    URGENTE: "bold red",
    SEMANA: "yellow",
    "MANUTENÇÃO": "cyan",
    OK: "green",
}


def render_list(rows: list[ListRow], today: date, console: Console) -> None:
    """Imprime a lista completa com seções e cores."""
    console.print(Text(f"Lista de compras — {format_date_pt(today)}", style="bold"))
    console.print()

    maint_rows = [r for r in rows if r.is_maintenance and r.priority != OK]
    consumable_rows = [r for r in rows if not r.is_maintenance]

    for key, header, is_maint in _SECTIONS:
        if is_maint:
            section_rows = maint_rows
        elif key == OK:
            section_rows = [r for r in consumable_rows if r.priority == OK] + [
                r for r in rows if r.is_maintenance and r.priority == OK
            ]
        else:
            section_rows = [r for r in consumable_rows if r.priority == key]

        console.print(Text(header, style=_STYLES[key]))
        if section_rows:
            for r in section_rows:
                console.print(_format_aligned(r))
        else:
            console.print("  —")
        console.print()


def render_plain(rows: list[ListRow]) -> str:
    """Modo --plain: só os itens acionáveis, uma linha cada, sem seção OK."""
    tag = {URGENTE: "URGENTE", SEMANA: "SEMANA"}
    lines: list[str] = []
    for r in rows:
        if r.is_maintenance and r.priority != OK:
            lines.append(f"[MANUTENÇÃO] {r.name} — {r.qty_label}")
        elif not r.is_maintenance and r.priority in tag:
            lines.append(f"[{tag[r.priority]}] {r.name} — {r.qty_label}")
    return "\n".join(lines)


def _pad(text: str, width: int) -> str:
    """Preenche até `width`, garantindo ao menos 2 espaços de separação."""
    if len(text) >= width:
        return text + "  "
    return text.ljust(width)


def _format_aligned(r: ListRow) -> str:
    """Linha de item com colunas alinhadas: nome / quantidade / detalhe."""
    return f"  {_pad(r.name, 22)}{_pad(r.qty_label, 16)}{r.detail}"


# Abreviações de medida não pluralizam (kg, ml...) e não usam "×".
_MEASURE_UNITS = {"kg", "g", "mg", "ml", "l", "un"}


def qty_label(quantity: int, unit: str) -> str:
    """Monta o rótulo de quantidade conforme a unidade.

    "500ml" -> "2 × 500ml"; "kg" -> "1 kg"; "pacote" -> "1 pacote" / "2 pacotes".
    """
    if unit[:1].isdigit():  # unidade com medida embutida, ex.: "500ml"
        return f"{quantity} × {unit}"
    if unit.lower() in _MEASURE_UNITS:
        return f"{quantity} {unit}"
    if quantity == 1:
        return f"{quantity} {unit}"
    return f"{quantity} {unit}s"


def dias(n: int) -> str:
    """'1 dia' / '2 dias'."""
    return f"{n} dia" if abs(n) == 1 else f"{n} dias"


def stock_label(stock: float) -> str:
    """Ex.: 1.0 -> '1 unidade'; 2.0 -> '2 unidades'."""
    n = math.floor(stock) if stock >= 0 else math.ceil(stock)
    # Mantém inteiro quando possível para casar com a saída do spec.
    value = int(stock) if float(stock).is_integer() else round(stock, 1)
    suffix = "unidade" if value == 1 else "unidades"
    return f"{value} {suffix}"
