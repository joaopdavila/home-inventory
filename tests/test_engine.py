"""Testes da engine de reposição e prioridade."""

from datetime import date, timedelta

import pytest

from home_inventory.database import Database
from home_inventory.engine import (
    current_stock,
    days_overdue,
    days_remaining,
    effective_rate,
    maintenance_priority,
    priority,
    quantity_to_buy,
)
from home_inventory.models import ConsumableItem


# -- testes mínimos obrigatórios do spec ---------------------------------


def test_days_remaining_normal():
    assert days_remaining(current_stock=2, rate=0.33) == pytest.approx(6.06, rel=0.01)


def test_days_remaining_zero_rate():
    assert days_remaining(current_stock=2, rate=0) == float("inf")


def test_quantity_to_buy_rounds_up():
    assert quantity_to_buy(current_stock=1.5, stock_target=4) == 3


def test_quantity_to_buy_minimum_one():
    assert quantity_to_buy(current_stock=3.9, stock_target=4) == 1


def test_days_overdue_past():
    last = date(2026, 2, 15)
    assert days_overdue(last, interval_days=90) > 0  # vencido


def test_days_overdue_future():
    last = date.today() - timedelta(days=10)
    assert days_overdue(last, interval_days=90) < 0  # ainda faltam dias


def test_priority_urgent():
    assert priority(days=2) == "URGENTE"


def test_priority_next_week():
    assert priority(days=7) == "SEMANA QUE VEM"


def test_priority_ok():
    assert priority(days=30) == "OK"


# -- testes adicionais: estoque, taxa e prioridade de manutenção ---------


def _consumable(**kw) -> ConsumableItem:
    defaults = dict(
        id="detergente",
        name="Detergente",
        type="consumable",
        unit="500ml",
        stock_target=4,
        initial_stock=2.0,
        consumption_rate=0.33,
    )
    defaults.update(kw)
    return ConsumableItem(**defaults)


def test_current_stock_initial_only():
    db = Database(":memory:")
    item = _consumable(initial_stock=2.0)
    assert current_stock(item, db) == 2.0


def test_current_stock_buy_and_use():
    db = Database(":memory:")
    item = _consumable(initial_stock=2.0)
    db.add_event("detergente", "buy", 2)
    db.add_event("detergente", "use", 1)
    assert current_stock(item, db) == 3.0


def test_current_stock_correction_is_new_baseline():
    db = Database(":memory:")
    item = _consumable(initial_stock=2.0)
    db.add_event("detergente", "buy", 5)  # antes da correção: ignorado
    db.add_event("detergente", "stock_correction", 1)  # novo baseline = 1
    db.add_event("detergente", "use", 1)  # depois: 1 - 1 = 0
    assert current_stock(item, db) == 0.0


def test_current_stock_goes_negative():
    db = Database(":memory:")
    item = _consumable(initial_stock=1.0)
    db.add_event("detergente", "use", 3)
    assert current_stock(item, db) == -2.0


def test_effective_rate_fallback_when_insufficient_history():
    db = Database(":memory:")
    db.add_event("detergente", "use", 1)
    db.add_event("detergente", "use", 1)  # apenas 2 eventos < mínimo de 3
    assert effective_rate("detergente", db, fallback=0.33) == 0.33


def test_effective_rate_derived_from_history():
    db = Database(":memory:")
    for _ in range(3):
        db.add_event("detergente", "use", 1)
    # 3 eventos hoje → ~3 unidades / 1 dia (mínimo) → taxa alta
    assert effective_rate("detergente", db, fallback=0.33) == pytest.approx(3.0)


def test_maintenance_priority_overdue():
    assert maintenance_priority(overdue=5) == "URGENTE"


def test_maintenance_priority_soon():
    assert maintenance_priority(overdue=-5) == "SEMANA QUE VEM"


def test_maintenance_priority_ok():
    assert maintenance_priority(overdue=-30) == "OK"
