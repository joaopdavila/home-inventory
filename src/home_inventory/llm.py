"""Fallback opcional de interpretação via Claude (Anthropic SDK).

Só é usado quando o parser de regras (`nlp.py`) fica em dúvida E há uma
`ANTHROPIC_API_KEY` no ambiente. Mantém o `anthropic` como dependência
opcional: o import é tardio e qualquer falha degrada para `None` (o bot então
pede esclarecimento ao usuário).
"""

from __future__ import annotations

import json
import os

from .catalog import Catalog
from .models import ConsumableItem
from .nlp import (
    BUY,
    DONE,
    HELP,
    LIST,
    OUT,
    STATUS,
    UNKNOWN,
    USE,
    Intent,
)

_ACTIONS = [LIST, BUY, USE, OUT, DONE, STATUS, HELP, UNKNOWN]
_DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM = (
    "Você interpreta mensagens curtas em português de um casal gerenciando o "
    "estoque doméstico. A partir da mensagem, identifique a ação pretendida e, "
    "quando houver, o item do catálogo e a quantidade.\n\n"
    "Ações possíveis:\n"
    "- list: pedir a lista de compras\n"
    "- buy: comprou/repôs um item consumível\n"
    "- use: usou/gastou um item consumível\n"
    "- out: o item consumível acabou (estoque vai a zero)\n"
    "- done: fez a manutenção de um item (troca/limpeza)\n"
    "- status: perguntar a situação de um item\n"
    "- help: pedir ajuda ou não está claro\n"
    "- unknown: não dá para entender\n\n"
    "Use exatamente os ids do catálogo abaixo. Se não houver item, use null. "
    "Para buy/use sem quantidade explícita, use 1."
)


def is_available() -> bool:
    """True se há chave de API configurada."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def interpret(message: str, catalog: Catalog) -> Intent | None:
    """Interpreta a mensagem via Claude. Retorna None em qualquer falha."""
    try:
        import anthropic
    except ImportError:
        return None

    item_ids = [item.id for item in catalog]
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": _ACTIONS},
            "item_id": {"anyOf": [{"type": "string", "enum": item_ids}, {"type": "null"}]},
            "quantity": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        },
        "required": ["action", "item_id", "quantity"],
        "additionalProperties": False,
    }

    model = os.environ.get("INV_LLM_MODEL", _DEFAULT_MODEL)
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=256,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM + "\n\nCatálogo:\n" + _catalog_text(catalog),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": message}],
        )
    except Exception:
        return None

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    action = data.get("action", UNKNOWN)
    item_id = data.get("item_id")
    quantity = data.get("quantity")
    if action in (BUY, USE) and item_id is not None and quantity is None:
        quantity = 1.0
    return Intent(
        action=action if action in _ACTIONS else UNKNOWN,
        item_id=item_id,
        quantity=float(quantity) if quantity is not None else None,
        confidence=0.95,
        raw=message,
    )


def _catalog_text(catalog: Catalog) -> str:
    lines = []
    for item in catalog:
        kind = "consumível" if isinstance(item, ConsumableItem) else "manutenção"
        lines.append(f"- {item.id}: {item.name} ({kind})")
    return "\n".join(lines)
