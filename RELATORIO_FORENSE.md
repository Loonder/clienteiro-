# Relatorio Forense de Publicacao

Data local da analise: 2026-05-22  
Repositorio: `Loonder/clienteiro`  
Branch analisada: `main`  
HEAD remoto no inicio da analise: `8b83460`

## Resumo Executivo

O projeto esta funcional e recuperavel para apresentacao, mas o historico Git remoto contem segredos reais. A arvore de trabalho local foi remediada para remover arquivos sensiveis do indice, trocar credenciais por variaveis de ambiente, atualizar dependencias vulneraveis e adicionar controles de publicacao.

Conclusao objetiva:

- O working tree remediado pode virar uma versao publica limpa.
- O historico atual de `origin/main` nao deve ser apresentado como repositorio publico seguro sem reescrita de historico ou criacao de um repositorio novo.
- Todos os segredos encontrados no historico devem ser rotacionados, mesmo que os arquivos tenham sido removidos depois.

## Evidencias Principais

### Achado F-001: credenciais PostgreSQL/Supabase no historico

Severidade: Critica  
Status atual: removido do working tree; ainda presente no historico remoto ate reescrita.

Arquivos envolvidos historicamente:

- `test_db.py`
- `test_pg.js`
- `Colhedores/.env.example`
- `Colhedores/harvest_enterprise.py`
- `whatsapp_bot/evolution.env`

Commits relevantes:

- `595ed83` em 2026-03-19: introduziu `Colhedores/.env.example` e `Colhedores/harvest_enterprise.py`.
- `2728811` em 2026-04-05: reintroduziu arquivos `Colhedores`.
- `59e68c0` em 2026-04-22: introduziu `test_db.py`, `test_pg.js` e `whatsapp_bot/evolution.env` com connection strings.

Impacto:

- Qualquer credencial nesses arquivos deve ser considerada exposta.
- Mesmo removida do HEAD, permanece acessivel via historico Git.

Acao obrigatoria:

- Rotacionar senha do banco Supabase/PostgreSQL.
- Revogar credenciais antigas.
- Reescrever historico ou publicar em repo novo limpo.

### Achado F-002: chave privada Google Cloud no historico

Severidade: Critica  
Status atual: arquivo ausente do HEAD; ainda presente no historico remoto.

Arquivo historico:

- `whatsapp_bot/google-credentials.json`

Commits relevantes:

- `2c81115` em 2026-03-16: adicionou `whatsapp_bot/google-credentials.json`.
- `595ed83` em 2026-03-19: removeu o arquivo do HEAD.

Impacto:

- A service account deve ser considerada comprometida.

Acao obrigatoria:

- Desabilitar ou excluir a chave antiga no Google Cloud IAM.
- Criar nova chave somente se necessario.
- Preferir segredo por variavel de ambiente (`GCLOUD_PRIVATE_KEY`) ou secret manager.

### Achado F-003: arquivos de runtime WhatsApp/Evolution versionados

Severidade: Alta  
Status atual: removidos do indice local e protegidos por `.gitignore`.

Arquivos:

- `whatsapp_bot/evolution.env`
- `whatsapp_bot/instance.json`
- `whatsapp_bot/qrcode.png`

Commit relevante:

- `59e68c0` em 2026-04-22.

Impacto:

- Pode expor dados de instancia, API key, conexao ou QR/sessao operacional.

Acao obrigatoria:

- Rotacionar API key da Evolution.
- Recriar/invalidar sessao WhatsApp se tiver sido usada.
- Manter esses arquivos apenas localmente.

### Achado F-004: ausencia de `.dockerignore`

Severidade: Media  
Status atual: corrigido.

Impacto:

- Sem `.dockerignore`, builds Docker poderiam enviar `.env`, bancos locais, sessoes, `.git` e caches ao contexto de build.

Acao aplicada:

- Criado `.dockerignore` bloqueando segredos, bancos, sessoes, caches, logs, node_modules e historico Git.

### Achado F-005: dependencias vulneraveis

Severidade: Alta  
Status atual: corrigido no working tree.

Antes:

- `gunicorn==21.2.0`
- `requests==2.32.3`
- `flask==3.0.3`
- `fpdf2==2.7.9`
- `python-dotenv==1.0.1`
- `pytest==8.2.2`
- lockfile Node com vulnerabilidades altas/moderadas.

Depois:

- `safety check -r requirements.txt`: 0 vulnerabilidades reportadas.
- `npm audit` no bot: 0 vulnerabilidades.
- `npm audit` no webhook da roleta: 0 vulnerabilidades.

## Correcoes Aplicadas no Working Tree

- `.gitignore` reforcado para segredos e runtime WhatsApp.
- `.dockerignore` criado.
- `README.md` reescrito para apresentacao e operacao.
- `SECURITY.md` criado.
- `.env.example` e `whatsapp_bot/.env.example` sanitizados.
- Defaults inseguros de `INTERNAL_API_KEY` removidos.
- `SECRET_KEY` e `INTERNAL_API_KEY` passam a ser obrigatorios em producao.
- `test_db.py` e `test_pg.js` passam a ler connection string via env.
- `whatsapp_bot/evolution.env`, `whatsapp_bot/instance.json` e `whatsapp_bot/qrcode.png` removidos do indice.
- Dependencias Python atualizadas e fixadas.
- Lockfiles Node auditaveis.
- Endpoints LGPD testados apos ajustes de CSRF para API JSON.
- Fallback do scraper compatibilizado com assinatura antiga/nova.

## Validacoes Executadas

```bash
pytest -q
# 44 passed

bandit -r app.py core services test_db.py -x tests -q --severity-level high
# sem achados high

safety check -r requirements.txt
# No known security vulnerabilities reported

npm --prefix whatsapp_bot audit --audit-level=high --omit=dev
# found 0 vulnerabilities

npm --prefix roulette_webhook audit --audit-level=high --omit=dev
# found 0 vulnerabilities

docker compose config --quiet
# configuracao valida; avisa se env local nao define Evolution
```

## Estado Atual do Risco

| Area | Working tree local | Historico remoto atual |
| --- | --- | --- |
| `.env` real | ignorado | nao rastreado no HEAD |
| PostgreSQL/Supabase | sanitizado | comprometido historicamente |
| Google Cloud key | sanitizado | comprometido historicamente |
| Evolution/WhatsApp runtime | removido do indice | comprometido historicamente |
| Dependencias Python | corrigidas | corrigidas apos commit |
| Dependencias Node | corrigidas | corrigidas apos commit |
| Docker build context | corrigido | corrigido apos commit |

## Decisao Recomendada Para a Apresentacao

Opcao mais segura e simples:

1. Rotacionar Supabase/PostgreSQL, Google Cloud e Evolution.
2. Criar repositorio novo publico, por exemplo `clienteiro-public`.
3. Copiar somente o working tree limpo, sem `.git`, `.env`, bancos, sessoes e logs.
4. Fazer um unico commit inicial.
5. Rodar checklist de seguranca.
6. Mostrar esse repositorio aos professores.

Utilitario preparado para isso:

```powershell
.\scripts\prepare_clean_public_repo.ps1 -OutputPath ..\clienteiro_public_clean -InitGit
```

Opcao preservando o repositorio atual:

1. Rotacionar todos os segredos.
2. Instalar `git-filter-repo`.
3. Remover historicamente:
   - `whatsapp_bot/google-credentials.json`
   - `whatsapp_bot/evolution.env`
   - `whatsapp_bot/instance.json`
   - `whatsapp_bot/qrcode.png`
   - `test_db.py`
   - `test_pg.js`
   - `Colhedores/.env.example`
   - `Colhedores/harvest_enterprise.py`
4. Force-push para `origin/main`.
5. Invalidar caches/forks se existirem.

## Fala Curta Para a Banca

"Antes da entrega fizemos uma auditoria forense do repositorio. Encontramos credenciais em historico Git, tratamos como incidente real, removemos os arquivos do codigo atual, reforcamos `.gitignore` e `.dockerignore`, eliminamos defaults inseguros, atualizamos dependencias vulneraveis, adicionamos uma politica de seguranca e validamos com testes, Bandit, Safety e npm audit. Para publicacao, a decisao correta e apresentar um historico limpo ou um repositorio publico recriado apos rotacao das credenciais."
