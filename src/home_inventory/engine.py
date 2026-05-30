"""Lógica de reposição e prioridade.

Funções puras sempre que possível, para facilitar os testes. As funções que
dependem do histórico recebem um `Database`.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from .database import Database
from .models import ConsumableItem

# Janelas de prioridade (dias restantes para consumíveis).
URGENT_DAYS = 3          # acaba em ≤ 3 dias
NEXT_WEEK_DAYS = 10      # acaba em 4–10 dias

# Janela de manutenção: vence em ≤ 7 dias entra em "semana que vem".
MAINTENANCE_SOON_DAYS = 7

# Histórico considerado para refinar a taxa de consumo.
HISTORY_WINDOW_DAYS = 30
MIN_EVENTS_FOR_RATE = 3

URGENTE = "URGENTE"
SEMANA = "SEMANA QUE VEM"
OK = "OK"


# -- consumíveis ----------------------------------------------------------


def days_remaining(current_stock: float, rate: float) -> float:
    """Dias até o estoque zerar dado o consumo diário."""
    if rate <= 0:
        return float("inf")
    return current_stock / rate


def quantity_to_buy(current_stock: float, stock_target: float) -> int:
    """Quantidade recomendada de compra, arredondada pra cima. Mínimo 1."""
    return max(1, math.ceil(stock_target - current_stock))


def current_stock(item: ConsumableItem, db: Database) -> float:
    """Estoque calculado a partir do catálogo + histórico de eventos.

    Baseline = `initial_stock` do YAML, ou o valor da correção de estoque
    (`stock_correction`) mais recente, que passa a ser o novo ponto de partida.
    A partir do baseline, somam-se as compras e subtraem-se os consumos
    registrados *depois* da correção.
    """
    events = db.events_for(item.id)

    baseline = float(item.initial_stock)
    start_index = 0
    for i, ev in enumerate(events):
        if ev.event_type == "stock_correction" and ev.quantity is not None:
            baseline = float(ev.quantity)
            start_index = i + 1

    stock = baseline
    for ev in events[start_index:]:
        if ev.quantity is None:
            continue
        if ev.event_type == "buy":
            stock += ev.quantity
        elif ev.event_type == "use":
            stock -= ev.quantity
    return stock


def effective_rate(item_id: str, db: Database, fallback: float) -> float:
    """Taxa de consumo (unidades/dia) derivada do histórico de eventos.

    Usa eventos `use` dos últimos 30 dias. Com pelo menos 3 eventos, a taxa é
    o total consumido dividido pelos dias de histórico (do primeiro evento na
    janela até hoje). Caso contrário, usa o `fallback` do YAML.
    """
    since = (datetime.now() - timedelta(days=HISTORY_WINDOW_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    use_events = [
        ev
        for ev in db.events_for(item_id, since=since)
        if ev.event_type == "use" and ev.quantity is not None
    ]

    if len(use_events) < MIN_EVENTS_FOR_RATE:
        return fallback

    total_used = sum(ev.quantity for ev in use_events)
    first_at = _parse_ts(use_events[0].created_at)
    days = max(1.0, (datetime.now() - first_at).total_seconds() / 86400.0)
    return total_used / days


def history_days(item_id: str, db: Database) -> int:
    """Dias de histórico de consumo na janela (para exibição no `status`)."""
    since = (datetime.now() - timedelta(days=HISTORY_WINDOW_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    use_events = [
        ev
        for ev in db.events_for(item_id, since=since)
        if ev.event_type == "use" and ev.quantity is not None
    ]
    if len(use_events) < MIN_EVENTS_FOR_RATE:
        return 0
    first_at = _parse_ts(use_events[0].created_at)
    return max(1, (datetime.now() - first_at).days)


# -- manutenção -----------------------------------------------------------


def days_overdue(last_done: date, interval_days: int) -> int:
    """Positivo = vencido há N dias. Negativo = faltam N dias."""
    next_due = last_done + timedelta(days=interval_days)
    return (date.today() - next_due).days


# -- prioridade -----------------------------------------------------------


def priority(days: float) -> str:
    """Classifica um consumível pelos dias restantes de estoque."""
    if days <= URGENT_DAYS:
        return URGENTE
    if days <= NEXT_WEEK_DAYS:
        return SEMANA
    return OK


def maintenance_priority(overdue: int) -> str:
    """Classifica um item de manutenção pelos dias de atraso/folga.

    `overdue` > 0 → vencido (URGENTE). Vence em ≤ 7 dias → SEMANA QUE VEM.
    """
    if overdue > 0:
        return URGENTE
    if -overdue <= MAINTENANCE_SOON_DAYS:
        return SEMANA
    return OK


def _parse_ts(value: str) -> datetime:
    """Interpreta timestamps do SQLite (com ou sem fração de segundo)."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # Último recurso: aceita ISO ("2026-05-30" ou "2026-05-30T..").
    return datetime.fromisoformat(value.replace("T", " ").split(".")[0])
