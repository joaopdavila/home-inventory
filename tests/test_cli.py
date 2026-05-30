"""Testes dos comandos do CLI via runner do Typer."""

import pytest
from typer.testing import CliRunner

from home_inventory import cli

runner = CliRunner()

CATALOG = """
items:
  - id: detergente
    name: Detergente
    type: consumable
    unit: "500ml"
    stock_target: 4
    initial_stock: 2
    consumption_rate: 0.33
  - id: papel-toalha
    name: Papel toalha
    type: consumable
    unit: "pacote"
    stock_target: 3
    initial_stock: 1
    consumption_rate: 0.14
  - id: filtro-ar
    name: Filtro do ar-condicionado
    type: maintenance
    interval_days: 90
    last_done: 2026-02-15
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    catalog = tmp_path / "items.yaml"
    catalog.write_text(CATALOG, encoding="utf-8")
    db = tmp_path / "inventory.db"
    monkeypatch.setattr(cli, "DEFAULT_CATALOG_PATH", catalog)
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", db)
    return tmp_path


def test_list_runs(env):
    result = runner.invoke(cli.app, ["list"])
    assert result.exit_code == 0
    assert "Lista de compras" in result.stdout
    assert "Detergente" in result.stdout


def test_list_plain(env):
    result = runner.invoke(cli.app, ["list", "--plain"])
    assert result.exit_code == 0
    assert "Lista de compras" not in result.stdout
    assert "OK" not in result.stdout
    # Filtro vencido aparece como manutenção.
    assert "[MANUTENÇÃO] Filtro do ar-condicionado" in result.stdout


def test_buy_updates_stock(env):
    result = runner.invoke(cli.app, ["buy", "detergente", "2"])
    assert result.exit_code == 0
    assert "Estoque atual: 4 unidades" in result.stdout


def test_use_updates_stock_and_warns_urgent(env):
    # initial_stock=1; consumindo 1 → estoque 0 → URGENTE.
    result = runner.invoke(cli.app, ["use", "papel-toalha", "1"])
    assert result.exit_code == 0
    assert "Estoque atual: 0 unidades" in result.stdout
    assert "⚠ URGENTE" in result.stdout


def test_buy_then_list_reflects_stock(env):
    runner.invoke(cli.app, ["buy", "detergente", "2"])
    result = runner.invoke(cli.app, ["status", "detergente"])
    assert result.exit_code == 0
    assert "Estoque atual:    4 × 500ml" in result.stdout


def test_done_resets_maintenance(env):
    result = runner.invoke(cli.app, ["done", "filtro-ar"])
    assert result.exit_code == 0
    assert "Próxima em" in result.stdout
    # Após registrar, o filtro deixa de estar vencido na lista.
    listing = runner.invoke(cli.app, ["list"])
    assert "vencido" not in listing.stdout


def test_unknown_item_errors(env):
    result = runner.invoke(cli.app, ["buy", "xpto", "1"])
    assert result.exit_code == 1
    assert "não encontrado em items.yaml" in result.output


def test_missing_catalog_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "DEFAULT_CATALOG_PATH", tmp_path / "nope.yaml")
    monkeypatch.setattr(cli, "DEFAULT_DB_PATH", tmp_path / "db.sqlite")
    result = runner.invoke(cli.app, ["list"])
    assert result.exit_code == 1
    assert "não encontrado" in result.output


def test_buy_maintenance_item_errors(env):
    result = runner.invoke(cli.app, ["buy", "filtro-ar", "1"])
    assert result.exit_code == 1
    assert "não é um item consumível" in result.output
