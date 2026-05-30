"""Testes do parser de linguagem natural (regras, sem LLM)."""

from datetime import date

import pytest

from home_inventory.catalog import Catalog
from home_inventory import nlp
from home_inventory.models import ConsumableItem, MaintenanceItem


@pytest.fixture
def catalog() -> Catalog:
    return Catalog(
        [
            ConsumableItem("detergente", "Detergente", "consumable", "500ml", 4, 2.0, 0.33),
            ConsumableItem("papel-toalha", "Papel toalha", "consumable", "pacote", 3, 1.0, 0.14),
            ConsumableItem("sabao-em-po", "Sabão em pó", "consumable", "kg", 2, 1.0, 0.1),
            MaintenanceItem("filtro-ar", "Filtro do ar-condicionado", "maintenance", 90, date(2026, 2, 15)),
            MaintenanceItem("pastilha-vaso", "Pastilha sanitária", "maintenance", 30, date(2026, 5, 1)),
        ]
    )


def test_parse_buy(catalog):
    intent = nlp.parse("comprei 2 detergentes", catalog)
    assert intent.action == nlp.BUY
    assert intent.item_id == "detergente"
    assert intent.quantity == 2.0


def test_parse_use_word_number(catalog):
    intent = nlp.parse("usei um papel toalha", catalog)
    assert intent.action == nlp.USE
    assert intent.item_id == "papel-toalha"
    assert intent.quantity == 1.0


def test_parse_out(catalog):
    intent = nlp.parse("acabou o sabão em pó", catalog)
    assert intent.action == nlp.OUT
    assert intent.item_id == "sabao-em-po"


def test_parse_done(catalog):
    intent = nlp.parse("troquei o filtro do ar", catalog)
    assert intent.action == nlp.DONE
    assert intent.item_id == "filtro-ar"


def test_parse_status(catalog):
    intent = nlp.parse("como está o detergente?", catalog)
    assert intent.action == nlp.STATUS
    assert intent.item_id == "detergente"


def test_parse_list(catalog):
    assert nlp.parse("lista", catalog).action == nlp.LIST
    assert nlp.parse("o que falta comprar", catalog).action == nlp.LIST


def test_parse_help(catalog):
    assert nlp.parse("ajuda", catalog).action == nlp.HELP
    assert nlp.parse("", catalog).action == nlp.HELP


def test_buy_defaults_to_one(catalog):
    intent = nlp.parse("comprei detergente", catalog)
    assert intent.action == nlp.BUY
    assert intent.quantity == 1.0


def test_unknown_action_low_confidence(catalog):
    intent = nlp.parse("blá blá blá coisa aleatória", catalog)
    assert intent.confidence < nlp._ITEM_MATCH_THRESHOLD or intent.action == nlp.UNKNOWN


def test_resolve_item_typo(catalog):
    # erro de digitação leve ainda resolve via fuzzy
    item_id, score = nlp.resolve_item(nlp.normalize("detergnte"), catalog)
    assert item_id == "detergente"
    assert score > 0.5


def test_extract_quantity_decimal(catalog):
    assert nlp.extract_quantity("usei 1,5 kg") == 1.5
    assert nlp.extract_quantity("comprei tres") == 3.0
    assert nlp.extract_quantity("sem numero aqui") is None
