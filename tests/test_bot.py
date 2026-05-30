"""Testes da lógica do bot (sem rede / sem Telegram / sem LLM)."""

from datetime import date

import pytest

from home_inventory import bot
from home_inventory.catalog import Catalog
from home_inventory.database import Database
from home_inventory.models import ConsumableItem, MaintenanceItem


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(
        [
            ConsumableItem("detergente", "Detergente", "consumable", "500ml", 4, 2.0, 0.33),
            ConsumableItem("papel-toalha", "Papel toalha", "consumable", "pacote", 3, 1.0, 0.14),
            ConsumableItem("sabao-em-po", "Sabão em pó", "consumable", "kg", 2, 1.0, 0.1),
            MaintenanceItem("filtro-ar", "Filtro do ar-condicionado", "maintenance", 90, date(2026, 2, 15)),
        ]
    )


@pytest.fixture
def db() -> Database:
    return Database(":memory:")


def test_buy_message(catalog, db):
    reply = bot.handle_message("comprei 2 detergentes", catalog, db)
    assert "Registrado: +2 × 500ml de Detergente" in reply
    assert "Estoque atual: 4 unidades" in reply


def test_use_message(catalog, db):
    reply = bot.handle_message("usei um papel toalha", catalog, db)
    assert "-1 pacote de Papel toalha" in reply
    assert "Estoque atual: 0 unidades" in reply


def test_out_message_zeroes_stock(catalog, db):
    reply = bot.handle_message("acabou o sabão em pó", catalog, db)
    assert "Sabão em pó acabou" in reply
    assert "Estoque atual: 0" in reply
    # estoque persistido como correção a zero
    from home_inventory import engine

    item = catalog.get("sabao-em-po")
    assert engine.current_stock(item, db) == 0.0


def test_done_message(catalog, db):
    reply = bot.handle_message("troquei o filtro do ar", catalog, db)
    assert "Filtro do ar-condicionado — troca em" in reply
    assert "Próxima em" in reply


def test_status_message(catalog, db):
    reply = bot.handle_message("como está o detergente?", catalog, db)
    assert "Detergente" in reply
    assert "Estoque atual" in reply


def test_list_message(catalog, db):
    reply = bot.handle_message("lista", catalog, db)
    assert "Lista de compras" in reply or "Tudo certo" in reply


def test_unknown_message_clarifies(catalog, db):
    reply = bot.handle_message("blá blá coisa aleatória", catalog, db)
    assert "Itens:" in reply  # mensagem de ajuda lista os ids


def test_out_on_maintenance_item_errors(catalog, db):
    # "acabou o filtro" não faz sentido (manutenção); deve avisar sem quebrar
    reply = bot.handle_message("acabou o filtro do ar", catalog, db)
    assert "⚠" in reply
