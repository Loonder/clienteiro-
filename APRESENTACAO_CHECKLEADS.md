# Clienteiro — Roteiro de Apresentação
### Vídeo Presencial · 5 minutos · ExpoTech 2026

---

> **Formato:** cada pessoa fala por volta de 1 minuto, em sequência.
> Falem com naturalidade, olhando para a câmera. Não precisam decorar palavra por palavra — entendam a ideia e falem com suas próprias palavras.
> A ordem sugerida está abaixo.

---

## ⏱️ ESTRUTURA DOS 5 MINUTOS

| Ordem | Quem | Tema | Tempo |
|---|---|---|---|
| 1º | **Você (Criador)** | Apresenta o projeto, o problema e a solução | ~1min 20s |
| 2º | **Rafael** | Design, identidade visual e experiência do usuário | ~55s |
| 3º | **Kevin** | Figma, prototipação e gestão do projeto (Kanban) | ~55s |
| 4º | **Miqueias** | Planejamento, testes e validação do produto | ~55s |
| 5º | **Lucas** | Banco de dados e encerramento | ~55s |

---

---

## 🎤 1º — VOCÊ (Criador) · ~1min 20s
**Tema: o projeto, o problema, a solução e a tecnologia**

---

> *"Olá, meu nome é [nome]. Eu sou o desenvolvedor do Clienteiro."*

> *"O Clienteiro é uma plataforma SaaS de prospecção automática de leads. O problema que ele resolve é simples: encontrar clientes para qualquer negócio é lento, caro e manual. Você passa horas no Google procurando empresas, ligando para números errados, comprando listas desatualizadas."*

> *"O Clienteiro faz isso automaticamente. Você informa o nicho — por exemplo, barbearia — e a cidade. O sistema varre o Google Maps, coleta o nome, o telefone real e a avaliação de cada negócio, calcula um score de qualidade de zero a cem, e entrega tudo num painel ao vivo. Sem intervenção humana."*

> *"Do ponto de vista técnico: o backend foi construído em Python com Flask, rodando em produção numa VPS da Hostinger dentro de Docker. O banco de dados é PostgreSQL hospedado no Supabase. O motor de colheita usa Selenium com ChromeDriver em modo invisível para navegar pelo Google Maps e extrair os dados. O sistema de qualificação dos leads usa Orientação a Objetos com o Padrão Strategy — cada tipo de lead tem seu próprio algoritmo de scoring. A segurança tem múltiplas camadas: proteção CSRF, rate limiting, cookies seguros e até armadilhas automáticas para bots. Tudo isso em produção, funcionando agora."*

---

---

## 🎤 2º — RAFAEL · ~55s
**Tema: design, identidade visual, vídeo e testes visuais**

---

> *"Meu nome é Rafael. Fui responsável pelo design visual do Clienteiro e pela produção do vídeo que vocês estão assistindo agora."*

> *"A identidade visual do projeto foi pensada para transmitir autoridade e confiança — algo que um produto SaaS premium precisa ter. Usamos uma estética inspirada em produtos Apple: tipografia Inter, paleta escura, e um efeito chamado glassmorphism, que são aquelas transparências foscas que você vê no painel. A ideia é que o visual não distraia — ele foca o usuário nos dados."*

> *"Também fui responsável pelos testes visuais do produto — verificar se as telas estavam se comportando corretamente em diferentes tamanhos, se os elementos estavam alinhados, se a experiência estava fluindo do jeito certo. Quando algo não estava bom visualmente, eu documentava e levava para o time corrigir."*

> *"O resultado é um produto que não parece um projeto de faculdade. Parece um produto real — porque é."*

---

---

## 🎤 3º — KEVIN · ~55s
**Tema: Figma, prototipação e Kanban**

---

> *"Meu nome é Kevin. Trabalhei na prototipação das telas no Figma e na organização do projeto com Kanban."*

> *"Antes de qualquer tela ser desenvolvida, ela passou pelo Figma. Lá a gente definiu o layout, o fluxo de navegação, os componentes visuais. Isso evita retrabalho — o desenvolvedor já sabe exatamente o que construir antes de escrever uma linha de código."*

> *"O Clienteiro tem dois contextos de uso muito diferentes: o modo kiosk, que é a tela de feira onde o visitante gira a roleta e cadastra o WhatsApp, e o painel administrativo, onde o gestor acompanha os leads em tempo real. Cada um teve seu fluxo prototipado separadamente no Figma, pensando no usuário de cada contexto."*

> *"Na parte de gestão, usamos Kanban para organizar as tarefas do projeto — o que estava a fazer, em andamento e concluído. Isso manteve o time alinhado e garantiu que nada ficasse esquecido durante o desenvolvimento."*

---

---

## 🎤 4º — MIQUEIAS · ~55s
**Tema: planejamento, testes e validação**

---

> *"Meu nome é Miqueias. Fui responsável pelo planejamento do projeto, pelos testes e pela validação do produto."*

> *"No planejamento, a gente mapeou os requisitos do sistema antes de começar a construir. Cada funcionalidade foi documentada com critérios claros de sucesso — o que significa que aquela feature está pronta, o que significa que ela falhou. Isso deu direção para o desenvolvimento e evitou que a gente construísse coisas que não eram necessárias."*

> *"Nos testes, eu validei os fluxos principais do sistema: o cadastro na roleta, o login no painel, o motor de colheita, a geração de relatório. Testei cenários de erro também — o que acontece quando o banco está fora, quando o usuário manda dado inválido, quando o motor é interrompido no meio da colheita. Esses testes foram fundamentais para garantir que o produto chegasse à feira funcionando."*

> *"Também participei da criação das telas no Figma, contribuindo com a visão de quem vai usar o produto — não só de quem vai construir."*

---

---

## 🎤 5º — LUCAS · ~55s
**Tema: banco de dados e encerramento**

---

> *"Meu nome é Lucas. Fui responsável pela estrutura do banco de dados do Clienteiro."*

> *"O banco é PostgreSQL, hospedado no Supabase. Ele armazena tudo: os leads coletados pelo motor, os usuários do sistema com seus níveis de acesso, um log de auditoria de todas as ações, e uma fila de eventos para o WhatsApp com sistema de retry automático — se o envio falhar, o sistema tenta de novo sozinho, com intervalos crescentes."*

> *"O modelo foi pensado para ser seguro e eficiente. Tem deduplicação automática — o mesmo lead não entra duas vezes. Tem conformidade com LGPD — os dados têm data de expiração e podem ser anonimizados sem apagar o histórico. E tem índices nas colunas mais consultadas para garantir que o painel carregue rápido mesmo com muitos leads."*

> *"Também participei dos testes e da prototipação no Figma. O Clienteiro é um projeto que a gente construiu com cuidado em cada camada — e o banco de dados é a fundação de tudo isso."*

> *"Obrigado."*

---

---

## 📋 DICAS PARA O DIA DA GRAVAÇÃO

- **Fundo:** parede limpa ou o painel do Clienteiro aberto atrás
- **Ordem:** grave em sequência, cada um fala sua parte e passa para o próximo
- **Tom:** confiante, direto, sem ler o papel — internalizem as ideias
- **Transição:** quem termina pode virar para o próximo ou o editor corta
- **Demo:** se quiser mostrar a tela durante a fala do criador, grave a tela separado e o editor coloca por cima

---

*Clienteiro · Python + Flask + PostgreSQL + Selenium · Docker na VPS Hostinger · 2026*
