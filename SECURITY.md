# Security Policy

## Escopo

Este repositorio contem a aplicacao Clienteiro, bot WhatsApp, webhook da roleta, templates web e scripts operacionais.

## Regras de Segredo

Nunca versionar:

- `.env` ou `.env.*` com valores reais.
- URLs PostgreSQL/Supabase com usuario e senha.
- Chaves privadas Google Cloud.
- API keys da Evolution, Gemini, Supabase ou servicos externos.
- QR codes, sessoes ou caches do WhatsApp.
- Bancos locais, logs e relatorios gerados.

Use apenas `.env.example` com placeholders `CHANGE_ME_*`.

## Checklist Antes de Publicar

```bash
git status --short --ignored
git ls-files | rg "(\\.env|\\.db|\\.sqlite|qrcode|instance\\.json|credentials|token|auth)"
rg -n --hidden -S "(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE KEY|DATABASE_URL|postgresql://)" -g "!.git" -g "!.venv" -g "!node_modules"
pytest -q
bandit -r app.py core services test_db.py -x tests -q --severity-level high
safety check -r requirements.txt
npm --prefix whatsapp_bot audit --audit-level=high --omit=dev
npm --prefix roulette_webhook audit --audit-level=high --omit=dev
docker compose config --quiet
```

## Resposta a Incidente

Se um segredo entrar no Git:

1. Trate como comprometido imediatamente.
2. Revogue/rotacione a credencial no provedor.
3. Remova do working tree e do indice.
4. Reescreva o historico antes de publicar ou continue em um repositorio novo limpo.
5. Force-push apenas depois de alinhar com todos os colaboradores.
6. Rode uma varredura completa em todos os refs, incluindo stash e tags.

## Publicacao Recomendada

Para apresentacao academica, a rota mais simples e segura e publicar um repositorio novo com um unico commit limpo, depois de validar que nenhuma credencial existe no working tree.

Utilitario local:

```powershell
.\scripts\prepare_clean_public_repo.ps1 -OutputPath ..\clienteiro_public_clean -InitGit
```

Para preservar o repositorio atual, use `git filter-repo` ou BFG para remover os caminhos historicos sensiveis, rotacione os segredos e force-push.
