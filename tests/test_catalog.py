"""Testes de leitura e validação do catálogo."""

from datetime import date

import pytest

from home_inventory.catalog import CatalogError, load_catalog
from home_inventory.models import ConsumableItem, MaintenanceItem

VALID_YAML = """
items:
  - id: detergente
    name: Detergente
    type: consumable
    unit: "500ml"
    stock_target: 4
    initial_stock: 2
    consumption_rate: 0.33
  - id: filtro-ar
    name: Filtro do ar-condicionado
    type: maintenance
    interval_days: 90
    last_done: 2026-02-15
"""


def _write(tmp_path, text):
    p = tmp_path / "items.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_valid_catalog(tmp_path):
    catalog = load_catalog(_write(tmp_path, VALID_YAML))
    assert len(catalog) == 2

    det = catalog.get("detergente")
    assert isinstance(det, ConsumableItem)
    assert det.unit == "500ml"
    assert det.stock_target == 4
    assert det.consumption_rate == pytest.approx(0.33)

    filtro = catalog.get("filtro-ar")
    assert isinstance(filtro, MaintenanceItem)
    assert filtro.interval_days == 90
    assert filtro.last_done == date(2026, 2, 15)


def test_missing_file_raises(tmp_path):
    with pytest.raises(CatalogError, match="não encontrado"):
        load_catalog(tmp_path / "nao-existe.yaml")


def test_unknown_item_raises(tmp_path):
    catalog = load_catalog(_write(tmp_path, VALID_YAML))
    with pytest.raises(CatalogError, match="Item 'xpto' não encontrado em items.yaml"):
        catalog.get("xpto")


def test_invalid_type_raises(tmp_path):
    bad = """
items:
  - id: x
    name: X
    type: wat
"""
    with pytest.raises(CatalogError, match="type inválido"):
        load_catalog(_write(tmp_path, bad))


def test_missing_required_field_raises(tmp_path):
    bad = """
items:
  - id: detergente
    name: Detergente
    type: consumable
    unit: "500ml"
    stock_target: 4
"""
    with pytest.raises(CatalogError, match="campos obrigatórios"):
        load_catalog(_write(tmp_path, bad))


def test_duplicate_id_raises(tmp_path):
    dup = VALID_YAML + """
  - id: detergente
    name: Outro
    type: consumable
    unit: "1l"
    stock_target: 1
    initial_stock: 0
    consumption_rate: 0.1
"""
    with pytest.raises(CatalogError, match="duplicado"):
        load_catalog(_write(tmp_path, dup))


def test_bad_date_raises(tmp_path):
    bad = """
items:
  - id: filtro
    name: Filtro
    type: maintenance
    interval_days: 90
    last_done: "not-a-date"
"""
    with pytest.raises(CatalogError, match="last_done inválido"):
        load_catalog(_write(tmp_path, bad))
