"""Interpretação de mensagens em linguagem natural (português).

Parser determinístico baseado em regras: detecta a ação por palavras-chave,
resolve o item por correspondência aproximada com o catálogo e extrai a
quantidade. Não precisa de rede nem de chave de API.

Quando a confiança fica baixa, o chamador (bot) pode recorrer a um fallback
com LLM — veja `llm.py`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .catalog import Catalog
from .models import ConsumableItem, MaintenanceItem

# Ações reconhecidas.
LIST = "list"
BUY = "buy"
USE = "use"
OUT = "out"        # "acabou" → zera o estoque (stock_correction = 0)
DONE = "done"
STATUS = "status"
HELP = "help"
UNKNOWN = "unknown"


@dataclass
class Intent:
    """Intenção interpretada a partir de uma mensagem."""

    action: str
    item_id: str | None = None
    quantity: float | None = None
    confidence: float = 1.0
    note: str | None = None  # explicação quando há ambiguidade/erro
    raw: str = ""


# Palavras-chave por ação (já normalizadas, sem acento).
_VERBS = {
    BUY: ("comprei", "compramos", "comprar", "compra", "trouxe", "cheguei", "adiciona", "repus", "abasteci"),
    USE: ("usei", "usamos", "gastei", "gastamos", "consumi", "peguei", "tirei", "usou"),
    OUT: ("acabou", "acabei", "acabaram", "zerou", "esgotou"),
    DONE: ("troquei", "trocamos", "trocado", "troca", "limpei", "fiz", "feito", "manutencao", "done"),
    STATUS: ("status", "situacao", "quanto", "como esta", "como ta", "resta", "tem de", "sobrou"),
    LIST: ("lista", "compras", "comprar?", "o que falta", "o que comprar", "preciso", "mercado"),
    HELP: ("ajuda", "help", "comandos", "start", "como usar", "o que voce faz"),
}

_NUMBER_WORDS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "meio": 0.5, "meia": 0.5,
}

# Confiança mínima para aceitar uma correspondência de item.
_ITEM_MATCH_THRESHOLD = 0.5


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, espaços colapsados."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def parse(message: str, catalog: Catalog) -> Intent:
    """Interpreta uma mensagem livre em uma `Intent`."""
    raw = message.strip()
    norm = normalize(raw)
    if not norm:
        return Intent(HELP, confidence=1.0, raw=raw)

    action, action_conf = _detect_action(norm)
    item_id, item_conf = resolve_item(norm, catalog)
    quantity = extract_quantity(norm)

    # Comandos sem item.
    if action in (LIST, HELP):
        return Intent(action, confidence=action_conf, raw=raw)

    # Se achou um item mas nenhuma ação clara, infere pelo tipo do item.
    if action == UNKNOWN and item_id is not None:
        action, action_conf = _infer_action_from_item(catalog, item_id, quantity)

    if action == UNKNOWN:
        return Intent(
            UNKNOWN,
            item_id=item_id,
            confidence=0.0,
            note="Não entendi a ação (comprar, usei, acabou, troquei, status...).",
            raw=raw,
        )

    if item_id is None:
        return Intent(
            action,
            quantity=quantity,
            confidence=min(action_conf, 0.4),
            note="Não identifiquei o item.",
            raw=raw,
        )

    if action in (BUY, USE) and quantity is None:
        quantity = 1.0  # padrão sensato: "comprei detergente" => 1

    confidence = min(action_conf, item_conf)
    return Intent(
        action,
        item_id=item_id,
        quantity=quantity,
        confidence=confidence,
        raw=raw,
    )


def _detect_action(norm: str) -> tuple[str, float]:
    """Detecta a ação por palavra-chave.

    Frases de várias palavras (ex.: "o que falta") são mais específicas e têm
    prioridade sobre palavras soltas (ex.: "comprar"). Dentro de cada passo a
    ordem importa: OUT/USE antes de BUY.
    """
    words = set(norm.split())
    order = (OUT, DONE, USE, BUY, STATUS, LIST, HELP)

    # 1) frases (mais específicas)
    for action in order:
        for kw in _VERBS[action]:
            if " " in kw and kw in norm:
                return action, 0.9

    # 2) palavras soltas
    for action in order:
        for kw in _VERBS[action]:
            if " " not in kw and kw in words:
                return action, 0.9

    return UNKNOWN, 0.0


def _infer_action_from_item(catalog: Catalog, item_id: str, quantity) -> tuple[str, float]:
    """Sem verbo claro, usa o tipo do item: manutenção → done, consumível → status."""
    item = catalog.get(item_id)
    if isinstance(item, MaintenanceItem):
        return DONE, 0.5
    if quantity is not None:
        return USE, 0.4
    return STATUS, 0.4


def resolve_item(norm: str, catalog: Catalog) -> tuple[str | None, float]:
    """Resolve o item mencionado por correspondência aproximada.

    Retorna (item_id, confiança). Combina overlap de palavras do nome e
    similaridade de sequência; exige limiar mínimo.
    """
    msg_words = [w for w in norm.split() if len(w) > 2]
    best_id: str | None = None
    best_score = 0.0

    for item in catalog:
        name_norm = normalize(item.name)
        id_norm = normalize(item.id.replace("-", " "))
        candidate_words = set(name_norm.split()) | set(id_norm.split())
        candidate_words = {w for w in candidate_words if len(w) > 2}

        # Overlap de palavras (palavra do nome aparece na mensagem).
        if candidate_words:
            overlap = sum(1 for w in candidate_words if w in norm)
            overlap_score = overlap / len(candidate_words)
        else:
            overlap_score = 0.0

        # Melhor similaridade fuzzy palavra-a-palavra (pega erros de digitação).
        # Só conta acima de um limiar alto, para não casar palavras só parecidas
        # (ex.: "aleatória" ~ "sanitária").
        fuzzy = 0.0
        for cw in candidate_words:
            for mw in msg_words:
                ratio = SequenceMatcher(None, cw, mw).ratio()
                if ratio >= 0.8:
                    fuzzy = max(fuzzy, ratio)

        score = max(overlap_score, fuzzy * 0.9)
        if score > best_score:
            best_score = score
            best_id = item.id

    if best_score >= _ITEM_MATCH_THRESHOLD:
        return best_id, min(1.0, best_score)
    return None, 0.0


def extract_quantity(norm: str) -> float | None:
    """Extrai uma quantidade: dígitos ('2', '1,5') ou número por extenso."""
    m = re.search(r"\d+(?:[.,]\d+)?", norm)
    if m:
        return float(m.group().replace(",", "."))
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", norm):
            return float(value)
    return None
