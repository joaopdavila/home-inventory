"""Bot do Telegram — backend de estoque compartilhado pela família.

Long polling (não precisa de URL pública). Aceita comandos apenas dos usuários
da allowlist. A lógica de interpretação/execução vive em `bot.py`; aqui ficam
só a fiação do python-telegram-bot e o controle de acesso.

Executar:
    export INV_TELEGRAM_TOKEN=123456:ABC...
    export INV_ALLOWED_USERS=11111111,22222222   # opcional, recomendado
    inv-bot

Webhook (alternativa, para deploy em nuvem): troque `run_polling()` por
`run_webhook(listen=..., port=..., webhook_url=...)`. Veja o README.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import bot as bot_logic
from .catalog import Catalog, load_catalog
from .config import BotConfig, load_bot_config
from .database import Database

logger = logging.getLogger("home_inventory.telegram")


def _reply_for(text: str, config: BotConfig, catalog: Catalog) -> str:
    """Abre o banco, processa a mensagem e devolve a resposta."""
    db = Database(config.db_path)
    try:
        return bot_logic.handle_message(
            text, catalog, db, use_llm=config.use_llm_fallback
        )
    finally:
        db.close()


def build_application(config: BotConfig) -> Application:
    """Monta a Application do Telegram com os handlers e o controle de acesso."""
    catalog = load_catalog(config.catalog_path)
    application = Application.builder().token(config.token).build()

    async def guard(update: Update) -> bool:
        user = update.effective_user
        if config.is_allowed(user.id if user else -1):
            return True
        await update.message.reply_text(
            "🚫 Você não tem acesso a este estoque.\n"
            f"Seu ID do Telegram é {user.id if user else '?'} — "
            "peça para adicioná-lo à allowlist."
        )
        return False

    async def on_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update):
            return
        await update.message.reply_text(
            bot_logic.HELP_TEXT, parse_mode=ParseMode.MARKDOWN
        )

    async def on_list(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update):
            return
        reply = _reply_for("lista", config, catalog)
        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

    async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await guard(update):
            return
        text = update.message.text or ""
        try:
            reply = _reply_for(text, config, catalog)
        except Exception:  # nunca derruba o bot por uma mensagem
            logger.exception("Falha ao processar mensagem")
            reply = "⚠ Algo deu errado ao processar isso. Tente de novo."
        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

    application.add_handler(CommandHandler(["start", "help", "ajuda"], on_help))
    application.add_handler(CommandHandler("list", on_list))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
    )
    return application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    config = load_bot_config()
    if not config.restricted:
        logger.warning(
            "INV_ALLOWED_USERS vazio: o bot aceitará comandos de QUALQUER pessoa. "
            "Defina a allowlist para restringir o acesso."
        )
    application = build_application(config)
    logger.info("Bot iniciado (long polling). Ctrl+C para encerrar.")
    application.run_polling()


if __name__ == "__main__":
    main()
