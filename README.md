# home-inventory

CLI em Python para rastrear estoque de itens domésticos (consumíveis e
manutenção), calcular automaticamente a prioridade de reposição e gerar uma
lista de compras acionável.

## Conceito

| Tipo          | Lógica de reposição                                                         |
|---------------|----------------------------------------------------------------------------|
| `consumable`  | Baseado em taxa de consumo medida, derivada do histórico de `use` e `buy`. |
| `maintenance` | Baseado em intervalo fixo (dias). Não tem estoque, tem data de última troca. |

O catálogo (`data/items.yaml`) é editado manualmente no setup e **nunca** é
alterado pelo CLI em runtime. O histórico de eventos vive em
`data/inventory.db` (SQLite), criado automaticamente no primeiro comando.

## Instalação

Requer Python ≥ 3.11.

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Isso instala o comando `inv`.

## Catálogo — `data/items.yaml`

```yaml
items:
  - id: detergente
    name: Detergente
    type: consumable
    unit: "500ml"
    stock_target: 4          # unidades que você quer ter em casa
    initial_stock: 2         # estoque no momento do setup
    consumption_rate: 0.33   # unidades/dia (estimativa; refinada pelo histórico)

  - id: filtro-ar
    name: Filtro do ar-condicionado
    type: maintenance
    interval_days: 90        # intervalo de troca recomendado
    last_done: 2026-02-15    # data da última troca (ISO 8601)
```

## Comandos

| Comando                     | O que faz                                                        |
|-----------------------------|------------------------------------------------------------------|
| `inv list`                  | Lista de compras priorizada (URGENTE / SEMANA / MANUTENÇÃO / OK). |
| `inv list --plain`          | Lista enxuta, sem headers — fácil de colar no WhatsApp.           |
| `inv buy <id> <qtd>`        | Registra compra e atualiza o estoque.                            |
| `inv use <id> <qtd>`        | Registra consumo; avisa se cair em zona URGENTE.                 |
| `inv done <id>`             | Registra manutenção feita e reseta o intervalo.                  |
| `inv stock`                 | Inventário interativo dos consumíveis (corrige o estoque).       |
| `inv status <id>`           | Histórico e projeção de um item.                                 |

### Exemplo

```text
$ inv list
Lista de compras — 30 mai 2026

URGENTE  (acaba em ≤ 3 dias ou manutenção vencida)
  Detergente            2 × 500ml       acaba em 2 dias

SEMANA QUE VEM  (acaba em 4–10 dias ou manutenção vence em ≤ 7 dias)
  Papel toalha          1 pacote        acaba em 6 dias
...
```

## Regras de prioridade

- **URGENTE**: dias restantes ≤ 3, ou item de manutenção vencido.
- **SEMANA QUE VEM**: dias restantes 4–10, ou manutenção vence em ≤ 7 dias.
- **OK**: acima disso.

Quantidade recomendada = `stock_target − estoque_atual`, arredondada pra cima
(mínimo 1).

## Taxa de consumo

A taxa (`unidades/dia`) é derivada dos eventos `use` dos últimos 30 dias. Com
menos de 3 eventos no período, o CLI usa o `consumption_rate` do YAML como
fallback.

## Bot do Telegram (backend compartilhado)

Dá pra usar um chat do Telegram como backend compartilhado entre você e sua
esposa: os dois falam com o mesmo bot, em **linguagem natural**, e todo
`buy`/`use`/`done` cai no mesmo `inventory.db`.

```
você:  comprei 2 detergentes
bot:   Registrado: +2 × 500ml de Detergente. Estoque atual: 4 unidades.

esposa: acabou o sabão em pó
bot:    Anotado: Sabão em pó acabou. Estoque atual: 0. ⚠ Adicionei à lista.

você:  lista
bot:   🛒 Lista de compras
       [SEMANA] Papel toalha — 2 pacotes
       ...
```

Entende frases como *"comprei 2 detergentes"*, *"usei um papel toalha"*,
*"acabou o sabão"*, *"troquei o filtro do ar"*, *"como está o detergente?"*,
*"lista"*. O reconhecimento é por regras (offline, sem custo). Se você
configurar uma `ANTHROPIC_API_KEY`, mensagens ambíguas caem num fallback
opcional via Claude.

### Setup

1. Crie um bot com o [@BotFather](https://t.me/botfather) e copie o token.
2. Descubra os IDs do Telegram (seu e da sua esposa) — fale com o
   [@userinfobot](https://t.me/userinfobot), ou rode o bot sem allowlist e
   mande qualquer mensagem: ele responde com o seu ID.
3. Configure o ambiente (veja `.env.example`):

   ```bash
   pip install -e ".[bot]"            # + ".[llm]" para o fallback via Claude
   export INV_TELEGRAM_TOKEN=123456:ABC...
   export INV_ALLOWED_USERS=11111111,22222222   # recomendado
   inv-bot
   ```

O bot roda por **long polling** — funciona em qualquer máquina sempre ligada
(Raspberry Pi, servidor caseiro, VPS, celular antigo com Termux), sem precisar
de URL pública. **Importante:** só aceita comandos dos IDs da allowlist; sem
ela, qualquer um que achar o bot tem acesso.

### Deploy com webhook (alternativa)

Para hospedar em nuvem (Railway/Fly/Render), troque `application.run_polling()`
por `application.run_webhook(listen=..., port=..., webhook_url=...)` em
`src/home_inventory/telegram_bot.py` e exponha um endpoint HTTPS público.

## Desenvolvimento

```bash
.venv/bin/pytest -q          # roda a suíte de testes
```

Estrutura:

```
src/home_inventory/
  models.py        # dataclasses do domínio
  database.py      # wrapper SQLite (sem ORM)
  catalog.py       # lê e valida items.yaml
  engine.py        # reposição e prioridade (lógica pura)
  service.py       # ações compartilhadas entre CLI e bot
  cli.py           # comandos (Typer)
  formatter.py     # formatação da lista
  nlp.py           # parser de linguagem natural (pt-BR)
  llm.py           # fallback opcional via Claude
  config.py        # configuração do bot (env)
  bot.py           # lógica do bot (independente do Telegram)
  telegram_bot.py  # runner do python-telegram-bot (long polling)
```
