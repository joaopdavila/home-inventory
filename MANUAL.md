# 🏠 Lista de Compras Esperta — Manual

Um ajudante no Telegram que **lembra o que está acabando em casa** e monta a
lista de compras pra você. Você não precisa anotar nada num papel: é só avisar
ele quando usar ou comprar alguma coisa, conversando normalmente.

---

## 📱 Como usar (é só conversar!)

Você fala com ele **dentro do Telegram**, como se estivesse mandando mensagem
pra uma pessoa. Não tem botão complicado, não tem menu. Você escreve com suas
próprias palavras e ele entende.

> 💡 **A regra é uma só:** sempre que você **usar**, **comprar** ou **acabar**
> alguma coisa, manda uma mensagem rápida pra ele. Pronto. Ele cuida do resto.

---

## 🗣️ O que você pode falar

| Quando você quer...                  | Escreva algo como...              |
| ------------------------------------ | --------------------------------- |
| 🛒 Comprou alguma coisa              | *"comprei 2 detergentes"*         |
| 🧴 Usou / gastou alguma coisa        | *"usei um papel toalha"*          |
| 🚫 Acabou uma coisa                  | *"acabou o sabão em pó"*          |
| 🔧 Trocou/limpou algo (manutenção)   | *"troquei o filtro do ar"*        |
| ❓ Quer saber como está um produto   | *"como está o detergente?"*       |
| 📋 Quer a lista de compras           | *"lista"*                         |
| 🆘 Esqueceu como usar                | *"ajuda"*                         |

Não precisa decorar nada certinho — pode escrever do seu jeito. "acabou o
sabão", "comprei dois detergente", "preciso da lista"... ele se vira. 😊

---

## 💬 Exemplos de conversa de verdade

**Pedindo a lista de compras:**

> **Você:** lista
>
> **Ele:** 🛒 Lista de compras
> [SEMANA] Detergente — 2 × 500ml
> [SEMANA] Papel toalha — 2 pacotes
> [SEMANA] Sabão em pó — 1 kg
> [MANUTENÇÃO] Filtro do ar-condicionado — trocar
> [MANUTENÇÃO] Pastilha sanitária — trocar

**Avisando que comprou:**

> **Você:** comprei 2 detergentes
>
> **Ele:** Registrado: +2 × 500ml de Detergente. Estoque atual: 4 unidades.

**Avisando que usou (e ele te avisa quando está acabando!):**

> **Você:** usei um papel toalha
>
> **Ele:** Registrado: -1 pacote de Papel toalha. Estoque atual: 0 unidades. ⚠ URGENTE

**Avisando que acabou:**

> **Você:** acabou o sabão em pó
>
> **Ele:** Anotado: Sabão em pó acabou. Estoque atual: 0. ⚠ Adicionei à lista.

**Avisando uma troca/manutenção:**

> **Você:** troquei o filtro do ar
>
> **Ele:** Registrado: Filtro do ar-condicionado — troca em 30/05. Próxima em 28/08.

**Perguntando sobre um produto:**

> **Você:** como está o detergente?
>
> **Ele:** Detergente
> Estoque atual: 4 × 500ml
> Acaba em: ~12 dias
> Comprar: 1 unidade

---

## 🛒 Como ler a lista de compras

Quando você pede **"lista"**, ele separa as coisas por urgência:

- **[URGENTE]** 🔴 — está acabando agora (compre hoje/amanhã).
- **[SEMANA]** 🟡 — vai acabar nos próximos dias (já põe no carrinho).
- **[MANUTENÇÃO]** 🔧 — coisas pra trocar/limpar (filtro, pastilha...).

Os números são **quanto comprar** pra repor o estoque de casa. Ex.:
*"Papel toalha — 3 pacotes"* = compre 3 pacotes.

> 💡 **Dica de ouro:** antes de ir ao mercado, manda *"lista"* e copia a
> resposta direto pro WhatsApp. Aí no mercado é só ir riscando. 🛍️

---

## ❓ Perguntas comuns

**E se eu escrever errado ou de um jeito diferente?**
Sem problema. Ele tenta entender mesmo assim. Se ficar em dúvida, ele pergunta
e te dá exemplos.

**Preciso avisar toda vez que uso uma coisa?**
Quanto mais você avisa, mais esperto ele fica e melhor ele acerta quando as
coisas vão acabar. Mas relaxa — não precisa ser perfeito. Avise quando lembrar,
principalmente quando **comprar** ou quando **acabar**.

**Os dois (você e seu marido) usam o mesmo?**
Sim! É **uma lista só, compartilhada**. Se ele avisa que comprou detergente, já
aparece atualizado pra você também. 👫

**Vou estragar alguma coisa se mexer?**
Não. Pode conversar à vontade. Se mandar uma mensagem que ele não entende, ele
só pede pra você explicar de outro jeito. Nada quebra.

---

## 🛠️ Só para o marido — configuração (uma vez só)

> Esta parte é técnica e só precisa ser feita **uma vez**. A esposa não precisa
> ver nada disto — pra ela é só o Telegram.

1. No Telegram, fale com o **@BotFather**, mande `/newbot`, dê um nome (ex.:
   "Lista de Casa") e **copie o token** que ele te der.
2. Descubra os **IDs do Telegram** de vocês dois (fale com o **@userinfobot**).
3. Numa máquina que fique sempre ligada (um Raspberry Pi, um PC velho, um
   servidorzinho na nuvem, ou um celular antigo com o app Termux), instale e
   rode:

   ```bash
   pip install -e ".[bot]"
   export INV_TELEGRAM_TOKEN=<o token do BotFather>
   export INV_ALLOWED_USERS=<seu_id>,<id_da_esposa>
   inv-bot
   ```

4. Pronto. Agora é só os dois mandarem mensagem pro bot no Telegram.

Os produtos que o bot acompanha ficam no arquivo `data/items.yaml` — é lá que
você cadastra/edita os itens da casa (nome, quanto quer ter em estoque, etc.).
Detalhes completos no `README.md`.
