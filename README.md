# 🤖 JobAgent — Agente Autônomo de Busca de Vagas

> Cansado de abrir LinkedIn e InfoJobs toda hora com medo de perder uma vaga boa. Então automatizei isso.

JobAgent é um agente Python que roda em background, busca vagas em tempo real nas principais plataformas, filtra as compatíveis com seu perfil e envia um email formatado automaticamente — sem você precisar abrir nenhum site.

![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?style=flat-square&logo=fastapi)
![Playwright](https://img.shields.io/badge/Playwright-scraping-orange?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-banco%20local-lightgrey?style=flat-square)

---

## 📬 Como funciona

```
LinkedIn + InfoJobs
       ↓
   Scraper (Playwright)
       ↓
   Filtro + Banco (SQLite)
       ↓
   Email automático (SMTP)
       ↓
   Dashboard (FastAPI + HTML)
```

1. O scheduler roda o pipeline a cada N horas (configurável)
2. O scraper busca vagas nas plataformas ativas
3. O filtro aplica keywords, blacklist, nível e modalidade
4. Vagas novas são salvas no banco e enviadas por email
5. O dashboard exibe tudo em tempo real

---

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Scraping | Python · Playwright · feedparser |
| Backend | FastAPI · APScheduler · Uvicorn |
| Banco | SQLite |
| Notificação | SMTP · Gmail |
| Dashboard | HTML · CSS · JavaScript vanilla |
| Deploy | Railway · Procfile |

---

## ⚙️ Configuração

### 1. Clone o repositório

```bash
git clone https://github.com/LucasZanellaClemente/vagas.git
cd vagas
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure as credenciais

Crie o arquivo `credenciais.json` (não sobe pro git):

```json
{
  "email_remetente": "seu@gmail.com",
  "senha_app": "sua_senha_de_app_gmail",
  "email_destinatario": "seu@gmail.com"
}
```

> Para gerar a senha de app do Gmail: Conta Google → Segurança → Verificação em duas etapas → Senhas de app

### 4. Configure os filtros

Crie o arquivo `config.json` (não sobe pro git):

```json
{
  "keywords": ["Data Analyst", "Analista de Dados", "Python", "SQL"],
  "blacklist": ["Sênior", "PJ Obrigatório", "Gerente"],
  "niveis": [],
  "modalidades": [],
  "salario_minimo": 0,
  "localizacao": "São Paulo, SP",
  "plataformas": ["linkedin", "infojobs"],
  "email": "seu@gmail.com",
  "frequencia_horas": 2,
  "notificar_antes": true,
  "pular_duplicatas": true
}
```

### 5. Rode o agente

```bash
python scheduler.py
```

Acesse o dashboard em: `http://localhost:8000`

---

## 📊 Dashboard

O dashboard permite:

- **Filtros** — configurar keywords, plataformas, nível e modalidade
- **Vagas Encontradas** — visualizar todas as vagas com botão "Aplicar agora"
- **Log de Atividade** — acompanhar o status do agente em tempo real
- **Rodar Agente** — disparar o pipeline manualmente

---

## 📁 Estrutura do projeto

```
vagas/
├── scraper.py          # Módulo 2 — busca vagas nas plataformas
├── filtro_banco.py     # Módulo 3 — filtra e salva no SQLite
├── notificacao.py      # Módulo 4 — envia email com as vagas
├── aplicador.py        # Módulo 5 — automação de candidatura
├── scheduler.py        # Módulo 6 — API FastAPI + APScheduler
├── job_agent_dashboard.html  # Dashboard web
├── requirements.txt
├── Procfile            # Deploy Railway
└── .gitignore
```

---

## 🔒 Segurança

Os arquivos abaixo estão no `.gitignore` e **nunca sobem pro repositório**:

- `credenciais.json` — email e senha do Gmail
- `config.json` — email pessoal e preferências
- `job_agent.db` — banco de dados local
- `vagas_*.json` — dados temporários

---

## 📈 Resultado

Após configurar, o agente envia emails como este automaticamente:

```
📬 JobAgent encontrou 18 vagas!
26/05/2026 às 10:36 · LinkedIn · InfoJobs

LINKEDIN - VAGA #1
Analista de Dados Junior — Capitani Group
📍 Guarulhos, SP | 🏷️ Júnior
[Aplicar agora →]
```

---

## 👨‍💻 Autor

**Lucas Zanella Clemente**
Estudante de Engenharia de Software — FIAP

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Lucas%20Zanella-blue?style=flat-square&logo=linkedin)](https://linkedin.com/in/lucaszanella)
[![GitHub](https://img.shields.io/badge/GitHub-LucasZanellaClemente-black?style=flat-square&logo=github)](https://github.com/LucasZanellaClemente)
