"""Lógica de tratamento de mensagens do bot (independente do Telegram).

`handle_message` recebe texto livre + catálogo + banco e devolve a resposta em
texto. É puro e testável: não importa o python-telegram-bot nem o anthropic no
topo. O fallback de LLM é acionado sob demanda.
"""

from __future__ import annotations

from . import llm, nlp, service
from .catalog import Catalog, CatalogError
from .database import Database

# Abaixo deste nível de confiança, tentamos o fallback de LLM (se disponível).
CONFIDENCE_THRESHOLD = 0.6

HELP_TEXT = (
    "🏠 *Estoque doméstico*\n"
    "Fale comigo em linguagem natural. Exemplos:\n"
    "• \"comprei 2 detergentes\"\n"
    "• \"usei um papel toalha\"\n"
    "• \"acabou o sabão em pó\"\n"
    "• \"troquei o filtro do ar\"\n"
    "• \"como está o detergente?\"\n"
    "• \"lista\" — lista de compras\n"
)


def interpret(text: str, catalog: Catalog, use_llm: bool) -> nlp.Intent:
    """Interpreta a mensagem por regras; recorre ao LLM se a confiança for baixa."""
    intent = nlp.parse(text, catalog)
    if intent.confidence < CONFIDENCE_THRESHOLD and use_llm and llm.is_available():
        llm_intent = llm.interpret(text, catalog)
        if llm_intent is not None:
            return llm_intent
    return intent


def handle_message(
    text: str, catalog: Catalog, db: Database, use_llm: bool = False
) -> str:
    """Interpreta e executa uma mensagem, devolvendo a resposta em texto."""
    intent = interpret(text, catalog, use_llm)

    if intent.action == nlp.HELP:
        return HELP_TEXT
    if intent.action == nlp.LIST:
        return _shopping_list(catalog, db)
    if intent.action == nlp.UNKNOWN:
        return _clarify(catalog, intent.note)

    if intent.item_id is None:
        return _clarify(catalog, intent.note or "Não identifiquei o item.")

    try:
        return _run_action(intent, catalog, db)
    except (CatalogError, service.ServiceError) as exc:
        return f"⚠ {exc}"


def _run_action(intent: nlp.Intent, catalog: Catalog, db: Database) -> str:
    action = intent.action
    item_id = intent.item_id
    qty = intent.quantity if intent.quantity is not None else 1.0

    if action == nlp.BUY:
        return service.register_buy(catalog, db, item_id, qty).message
    if action == nlp.USE:
        return service.register_use(catalog, db, item_id, qty).message
    if action == nlp.OUT:
        return _mark_out(catalog, db, item_id)
    if action == nlp.DONE:
        return service.register_done(catalog, db, item_id).message
    if action == nlp.STATUS:
        return "\n".join(service.status_lines(catalog, db, item_id))
    return _clarify(catalog, "Não entendi a ação.")


def _mark_out(catalog: Catalog, db: Database, item_id: str) -> str:
    """'acabou o X' → zera o estoque via stock_correction."""
    item = catalog.get(item_id)
    if item.type != "consumable":
        raise service.ServiceError(f"'{item_id}' não é um item consumível.")
    service.record_stock_correction(db, item_id, 0.0, note="bot: acabou")
    return f"Anotado: {item.name} acabou. Estoque atual: 0. ⚠ Adicionei à lista."


def _shopping_list(catalog: Catalog, db: Database) -> str:
    body = service.shopping_list_plain(catalog, db)
    if not body:
        return "✅ Tudo certo — nada para comprar agora."
    return "🛒 *Lista de compras*\n" + body


def _clarify(catalog: Catalog, note: str | None) -> str:
    ids = ", ".join(item.id for item in catalog)
    prefix = f"{note} " if note else ""
    return (
        f"🤔 {prefix}Tente algo como \"comprei 2 detergentes\" ou \"lista\".\n"
        f"Itens: {ids}"
    )
