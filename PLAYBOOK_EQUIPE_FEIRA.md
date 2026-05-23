# Playbook da Equipe - Feira

## Objetivo

Todo mundo precisa explicar o mesmo produto com a mesma mensagem:

- problema
- solucao
- diferencial
- prova
- fechamento

## Mensagem central

Clienteiro nao e "mais um site".
Clienteiro e um sistema que transforma captura em acao comercial com visibilidade executiva em tempo real.

## Papeis da equipe

### Pessoa 1 - Abertura

Responsabilidade:
- contextualizar a dor do mercado
- explicar o problema em 30-40 segundos

Fala base:
"Hoje muita empresa ate gera interesse, mas perde dinheiro porque o lead entra sem qualificacao, sem prioridade e sem velocidade de resposta."

### Pessoa 2 - Produto

Responsabilidade:
- demonstrar o fluxo
- mostrar live e admin

Fala base:
"Aqui a captura entra, o score organiza prioridade, o painel ao vivo mostra operacao em tempo real e o admin transforma isso em decisao."

### Pessoa 3 - Negocio

Responsabilidade:
- traduzir tecnologia em ROI
- responder CEO e banca

Fala base:
"Nosso foco nao e volume vazio. Nosso foco e diminuir CAC desperdicado, acelerar resposta comercial e aumentar a conversao de leads realmente aproveitaveis."

### Pessoa 4 - Governanca

Responsabilidade:
- responder sobre LGPD, auditoria, seguranca e operacao

Fala base:
"O projeto foi pensado com consentimento rastreavel, canal de direitos do titular, retencao e trilha de auditoria. Nao e growth sem governanca."

## Estrutura da demo

1. Dor do mercado
2. Captura no kiosk
3. Lead aparecendo no live
4. Painel admin e score
5. LGPD e auditoria
6. Fechamento com ROI

## Regras de apresentacao

1. Ninguem fala "site".
2. Ninguem fala "projeto da faculdade" como argumento principal.
3. Ninguem inventa metrica que a tela nao mostra.
4. Ninguem entra em detalhe tecnico antes da dor e do ROI.
5. Se travar, volta para:
   - problema
   - valor
   - diferencial

## Palavras que ajudam

- previsibilidade comercial
- operacao em tempo real
- governanca de dados
- velocidade de resposta
- qualificacao de lead
- modo evento e modo diario

## Palavras que enfraquecem

- "so um dashboard"
- "so um bot"
- "so um scraper"
- "a gente pensou em"
- "ainda nao esta pronto"

## Encerramento padrao

"Nosso objetivo foi construir um sistema que ajude empresas a transformar interesse em conversa comercial qualificada, com visibilidade executiva e governanca desde o inicio."

## Operacao Kiosk Seguro (evento)

Para o kiosk de apresentacao:

1. Abrir sempre em `/kiosk`.
2. A tela roda em modo protegido com fullscreen forcado.
3. Atalhos comuns ficam bloqueados (F1-F12, Ctrl+*, Alt+*, Win+* e menu de contexto).
4. Saida administrativa somente com combo secreto + PIN.
5. Ao finalizar uma coleta, o kiosk se auto-reseta em alguns segundos para o proximo da fila (sem clique manual).

Configuracao no `.env`:

- `KIOSK_SECRET_COMBO=CTRL+SHIFT+U`
- `KIOSK_EXIT_PIN=7391` (trocar antes da feira)
- `KIOSK_UNLOCK_WINDOW_SECONDS=60`
- `KIOSK_UNLOCK_MAX_ATTEMPTS=5`

Importante:

- `Alt+Tab` e combinacoes de seguranca do sistema operacional nao podem ser bloqueadas 100% apenas por pagina web.
- Para bloqueio total em notebook de apresentacao, use conta Windows em modo Kiosk/Assigned Access.
