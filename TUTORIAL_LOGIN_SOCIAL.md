# Tutorial Completo: Gerar Credenciais Google/Facebook para Login Social

Data de referência: 22/04/2026.

Este guia é prático, no estilo "faça isso agora", para você sair com as credenciais prontas e funcionando no Clienteiro.

## O que você vai ter no final

- `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`
- `FACEBOOK_APP_ID` e `FACEBOOK_APP_SECRET`
- Redirect URLs configuradas corretamente
- Variáveis no `.env` prontas para usar no backend

---

## 0) Pré-requisitos

Antes de começar:

1. Ter domínio público do projeto (ex.: `https://clienteiro.com.br`).
2. Saber a URL de callback que o backend vai usar:
   - Google: `https://clienteiro.com.br/auth/google/callback`
   - Facebook: `https://clienteiro.com.br/auth/facebook/callback`
3. Ter acesso admin:
   - Google Cloud Console
   - Meta for Developers

---

## 1) Google OAuth (passo a passo clicando)

## 1.1 Criar/selecionar projeto

1. Acesse: `https://console.cloud.google.com`
2. No topo, clique no seletor de projeto.
3. Crie um projeto novo (ou use um existente).

## 1.2 Configurar OAuth Consent Screen

1. Menu esquerdo -> `APIs & Services` -> `OAuth consent screen`.
2. User Type:
   - Para uso interno da sua organização Google Workspace: `Internal`
   - Para qualquer conta Google: `External`
3. Preencha:
   - App name: `Clienteiro`
   - User support email: seu email
   - Developer contact email: seu email
4. Salve.
5. Em `Scopes`, adicione pelo menos:
   - `openid`
   - `email`
   - `profile`
6. Se estiver em `External` e modo testing:
   - Adicione `Test users` (seu email e quem vai testar).

## 1.3 Criar credencial OAuth

1. Menu -> `APIs & Services` -> `Credentials`.
2. Clique em `Create Credentials` -> `OAuth client ID`.
3. Application type: `Web application`.
4. Nome: `Clienteiro Web`.
5. Authorized JavaScript origins:
   - `https://clienteiro.com.br`
6. Authorized redirect URIs:
   - `https://clienteiro.com.br/auth/google/callback`
7. Clique `Create`.
8. Copie:
   - `Client ID`
   - `Client Secret`

Guarde esses valores com cuidado.

---

## 2) Facebook Login (Meta) passo a passo

## 2.1 Criar App no Meta

1. Acesse: `https://developers.facebook.com`
2. `My Apps` -> `Create App`.
3. Tipo sugerido: `Consumer` (ou tipo equivalente para Facebook Login web).
4. Nome do app: `Clienteiro`.
5. Crie o app e valide senha/2FA quando solicitado.

## 2.2 Adicionar produto Facebook Login

1. No painel do app, clique `Add Product`.
2. Escolha `Facebook Login`.
3. Clique em `Set Up`.

## 2.3 Configurar OAuth Web

1. Vá em `Facebook Login` -> `Settings`.
2. Em `Valid OAuth Redirect URIs`, adicione:
   - `https://clienteiro.com.br/auth/facebook/callback`
3. Salve.

## 2.4 Configurações básicas do app

1. Menu `Settings` -> `Basic`.
2. Copie:
   - `App ID`
   - `App Secret` (clicar em Show)
3. Em `App Domains`, adicione:
   - `clienteiro.com.br`
4. Em `Privacy Policy URL`, informe URL válida (ex.: `/privacy`).
5. Salve.

Observação:
- Em modo Development, só usuários com papel no app conseguem logar.
- Para público geral, publicar o app após validações do Meta.

---

## 3) Variáveis `.env` no backend

No servidor (`/root/clienteiro/.env`), adicione:

```env
APP_BASE_URL=https://clienteiro.com.br

GOOGLE_CLIENT_ID=cole_aqui
GOOGLE_CLIENT_SECRET=cole_aqui
GOOGLE_REDIRECT_URI=https://clienteiro.com.br/auth/google/callback

FACEBOOK_APP_ID=cole_aqui
FACEBOOK_APP_SECRET=cole_aqui
FACEBOOK_REDIRECT_URI=https://clienteiro.com.br/auth/facebook/callback

OAUTH_STATE_TTL_SECONDS=600
```

Depois de salvar:

```bash
cd /root/clienteiro
docker compose up -d --build backend
docker compose logs --tail=100 backend
```

---

## 4) Checklist rápido de validação

1. Abrir `/login`.
2. Clicar `Google`.
3. Conferir se redireciona para consentimento Google.
4. Voltar para callback sem erro de redirect URI.
5. Repetir com `Facebook`.

Se travar em qualquer etapa, veja seção de erros comuns abaixo.

---

## 5) Erros comuns (e como resolver)

## Google: `redirect_uri_mismatch`

Causa:
- URL no Google não bate 100% com URL enviada pelo backend.

Correção:
- Conferir exatamente protocolo, domínio e caminho:
  - `https://clienteiro.com.br/auth/google/callback`

## Google: `access blocked` / app em testing

Causa:
- Conta não está na lista de test users.

Correção:
- Adicionar usuário em `OAuth consent screen` -> `Test users`.

## Facebook: `URL blocked` ou erro de redirect

Causa:
- Callback não cadastrada em `Valid OAuth Redirect URIs`.

Correção:
- Cadastrar URL exata:
  - `https://clienteiro.com.br/auth/facebook/callback`

## Facebook: só admin consegue logar

Causa:
- App em modo Development.

Correção:
- Testar com conta que tenha papel no app ou publicar app.

---

## 6) Próximo passo no código (quando quiser que eu implemente)

Para funcionar de ponta a ponta no backend, faltam rotas OAuth reais:

- `GET /auth/google` e `/auth/google/callback`
- `GET /auth/facebook` e `/auth/facebook/callback`

Com:
- geração/validação de `state`
- troca de `code` por token
- leitura de perfil (id/email/nome)
- vínculo/criação de usuário em `gestores`
- criação de sessão normal

Se você quiser, no próximo passo eu já implemento o fluxo Google completo primeiro (mais rápido de validar), depois replico para Facebook.
