"""Configuração do bot a partir de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import DEFAULT_CATALOG_PATH
from .database import DEFAULT_DB_PATH


@dataclass
class BotConfig:
    """Parâmetros de execução do bot do Telegram."""

    token: str
    allowed_users: set[int] = field(default_factory=set)
    catalog_path: Path = Path(DEFAULT_CATALOG_PATH)
    db_path: Path = Path(DEFAULT_DB_PATH)
    use_llm_fallback: bool = False

    @property
    def restricted(self) -> bool:
        """True se há allowlist (o bot recusa quem não está nela)."""
        return bool(self.allowed_users)

    def is_allowed(self, user_id: int) -> bool:
        return not self.restricted or user_id in self.allowed_users


def _parse_ids(raw: str | None) -> set[int]:
    if not raw:
        return set()
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.add(int(part))
    return ids


def load_bot_config(env: dict[str, str] | None = None) -> BotConfig:
    """Lê a configuração do ambiente.

    Variáveis:
      INV_TELEGRAM_TOKEN   (obrigatória) — token do @BotFather
      INV_ALLOWED_USERS    — IDs do Telegram separados por vírgula (allowlist)
      INV_CATALOG          — caminho do items.yaml (padrão data/items.yaml)
      INV_DB               — caminho do banco (padrão data/inventory.db)
      ANTHROPIC_API_KEY    — se presente, habilita o fallback com Claude
    """
    env = env if env is not None else dict(os.environ)

    token = env.get("INV_TELEGRAM_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "INV_TELEGRAM_TOKEN não definido. Crie um bot com o @BotFather e "
            "exporte o token: export INV_TELEGRAM_TOKEN=123456:ABC..."
        )

    return BotConfig(
        token=token,
        allowed_users=_parse_ids(env.get("INV_ALLOWED_USERS")),
        catalog_path=Path(env.get("INV_CATALOG", str(DEFAULT_CATALOG_PATH))),
        db_path=Path(env.get("INV_DB", str(DEFAULT_DB_PATH))),
        use_llm_fallback=bool(env.get("ANTHROPIC_API_KEY", "").strip()),
    )
