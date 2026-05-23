# 🚜 Guia do Grupo: Colheita de Leads (CheckLeads)

Para chegarmos nos **100.000 leads**, vamos dividir o esforço! Cada um de nós vai rodar o robô em seu computador, focando em **nichos diferentes** para não haver bloqueios ou dados duplicados.

---

### 📦 1. O que você precisa instalado
No seu terminal (CMD, PowerShell ou VS Code), instale a biblioteca de busca:
```bash
pip install duckduckgo_search
```

---

### 🚀 2. Como Rodar (Escolha seu Grupo)
Cada participante do grupo deve rodar **UM comando diferente** para que os nichos não se cruzem.

> [!IMPORTANT]
> **Defina quem é qual Worker abaixo** e rode o comando correspondente:

| Integrante | Comando para rodar | Nichos que vai mapear (6 por pessoa) |
| :--- | :--- | :--- |
| **Worker 1** | `python harvest_leads.py 1` | Dentista, Advogado, Academia, Restaurante, Pizzaria, Pet Shop |
| **Worker 2** | `python harvest_leads.py 2` | Salão de Beleza, Barbearia, Oficina Mecânica, Imobiliária, Contabilidade, Escola Infantil |
| **Worker 3** | `python harvest_leads.py 3` | Clínica Estética, Informática, Arquitetura, Autoescola, Gráfica, Fotógrafo |
| **Worker 4** | `python harvest_leads.py 4` | Lavanderia, Farmácia, Ótica, Floricultura, Concessionária, Papelaria |
| **Worker 5** | `python harvest_leads.py 5` | Mercado, Chaveiro, Costureira, Loja de Celular, Bicicletaria, Sorveteria |

---

### 💾 3. Como me enviar os dados no final
O script cria/alimenta um arquivo automaticamente no caminho:
`../data/database.sqlite` (ou dentro da pasta `data` do seu projeto).

1. Deixe rodando o tempo que puder.
2. Quando quiser parar, aperte `CTRL + C`.
3. **Me envie o arquivo `database.sqlite`** que o robô gerou!

---

### 🔗 4. (Para o Administrador) Como Juntar Tudo
Quando receber os arquivos dos amigos (ex: `db_paulo.sqlite`, `db_lucas.sqlite`), use o script de fusão:
```bash
python merge_db.py data/database.sqlite data/db_paulo.sqlite
```
O script vai injetar todos os leads novos ignorando duplicidades de links!
