"""Testes da configuração do bot."""

import pytest

from home_inventory.config import load_bot_config


def test_token_required():
    with pytest.raises(RuntimeError, match="INV_TELEGRAM_TOKEN"):
        load_bot_config(env={})


def test_parses_allowlist():
    cfg = load_bot_config(
        env={"INV_TELEGRAM_TOKEN": "123:abc", "INV_ALLOWED_USERS": "111, 222 ;333"}
    )
    assert cfg.allowed_users == {111, 222, 333}
    assert cfg.restricted is True
    assert cfg.is_allowed(111)
    assert not cfg.is_allowed(999)


def test_unrestricted_when_no_allowlist():
    cfg = load_bot_config(env={"INV_TELEGRAM_TOKEN": "123:abc"})
    assert cfg.restricted is False
    assert cfg.is_allowed(12345)  # qualquer um é aceito


def test_llm_fallback_flag_follows_api_key():
    with_key = load_bot_config(
        env={"INV_TELEGRAM_TOKEN": "123:abc", "ANTHROPIC_API_KEY": "sk-ant-x"}
    )
    assert with_key.use_llm_fallback is True

    without = load_bot_config(env={"INV_TELEGRAM_TOKEN": "123:abc"})
    assert without.use_llm_fallback is False
