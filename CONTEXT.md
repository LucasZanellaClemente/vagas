# JobAgent — Contexto do Projeto

## O que é
Agente Python que busca e aplica para vagas de emprego automaticamente
nas plataformas LinkedIn, Indeed, Gupy e Glassdoor, com filtros configuráveis
via dashboard web e notificação por email.

## Perfil do usuário
- Nome: Lucas
- Estudante de Engenharia de Software na FIAP (São Paulo)
- Buscando estágio ou vaga júnior em Data Analysis, Data Engineering ou Frontend
- Localização: São Paulo, SP
- Filtros ativos: Estágio + Júnior | Remoto + Híbrido | Salário mínimo R$ 1.500
- Keywords: Data Analyst, Data Engineer, Python, SQL, Frontend
- Blacklist: Sênior, PJ Obrigatório

## Arquitetura geral
```
job_agent/
├── job_agent_dashboard.html  ✅ Módulo 1 — Interface de configuração de filtros
├── scraper.py                ✅ Módulo 2 — Scraper com Playwright (4 plataformas)
├── filtro_banco.py           ✅ Módulo 3 — Filtro avançado + banco SQLite
├── notificacao.py            ✅ Módulo 4 — Email HTML via Gmail SMTP
├── aplicador.py              ✅ Módulo 5 — Aplicador (LinkedIn Easy Apply + Gupy)
├── scheduler.py              ✅ Módulo 6 — Scheduler APScheduler + FastAPI + Railway
├── config.json               ✅ Configuração dos filtros (gerada pelo dashboard)
├── email_config.json         ⚠️  Criar manualmente (credenciais Gmail — não vai pro git)
├── requirements.txt          ✅
├── CONTEXT.md                ✅ Este arquivo
└── .gitignore                ✅
```

## Stack
- Python 3.11+
- Playwright (scraping + automação de formulários)
- SQLite (banco local via sqlite3 nativo)
- Gmail SMTP via smtplib (notificações)
- APScheduler (agendamento — Módulo 6)
- FastAPI opcional (API para o dashboard — Módulo 6)

## Fluxo de execução
```
[Dashboard] configura filtros → salva config.json
      ↓
[Módulo 2] scraper.py        → raspa vagas das 4 plataformas
      ↓                         salva: vagas_encontradas.json
[Módulo 3] filtro_banco.py   → deduplica (hash MD5) + filtra
      ↓                         salva: vagas_aprovadas.json + job_agent.db
[Módulo 4] notificacao.py    → envia email HTML com vagas aprovadas
      ↓                         usuário responde: "APLICAR TUDO" ou "APLICAR 1,3"
[Módulo 5] aplicador.py      → aplica nas vagas aprovadas (Easy Apply / Gupy)
      ↑
[Módulo 6] scheduler.py      → orquestra tudo a cada N horas + deploy Railway
```

## Módulos prontos — resumo técnico

### Módulo 1 — Dashboard (job_agent_dashboard.html)
- HTML/CSS/JS puro, sem framework
- Responsivo (mobile drawer, tablet 2 cols, desktop sidebar)
- Controles: plataformas, keywords, blacklist, nível, modalidade, salário (slider),
  toggles de comportamento, frequência de execução
- Salva config via botão (futuramente POST para FastAPI)

### Módulo 2 — Scraper (scraper.py)
- Usa Playwright async com Chromium headless
- Anti-detecção básica: user-agent customizado, viewport, locale pt-BR
- LinkedIn: listagem pública, scroll automático, sem login
- Indeed: seletores do Indeed Brasil, captura salário quando disponível
- Gupy: API REST pública (portal.api.gupy.io) — mais confiável que HTML
- Glassdoor: headless com fechamento automático de modal de login
- Funções utilitárias: extrair_salario(), detectar_nivel(), detectar_modalidade()
- Output: vagas_encontradas.json (lista de dicts)

### Módulo 3 — Filtro & Banco (filtro_banco.py)
- Dataclass Vaga com campos: titulo, empresa, localizacao, salario, nivel,
  modalidade, plataforma, url, descricao, data_coleta, status, hash_id
- Hash MD5 por (titulo + empresa + plataforma) para deduplicação
- SQLite com tabelas: vagas (status: nova/notificada/aplicada/ignorada) + execucoes
- Filtros com motivo de rejeição: blacklist, keyword, nível, modalidade, salário
- Função estatisticas() retorna resumo para o dashboard
- Output: vagas_aprovadas.json + job_agent.db

### Módulo 4 — Notificação (notificacao.py)
- Email HTML responsivo com cards por vaga (badge de plataforma, nível, modalidade)
- Versão texto puro como fallback
- Gmail SMTP via smtplib + TLS (porta 587)
- Credenciais em email_config.json (fora do git)
- Sistema de aprovação por resposta: "APLICAR TUDO" ou "APLICAR 1,3"
- Atualiza status das vagas para "notificada" no banco após envio

### Módulo 5 — Aplicador (aplicador.py) ✅
- LinkedIn Easy Apply: login + formulário multi-step (até 6 etapas)
- Gupy: candidatura nativa, pula redirecionamentos externos
- Indeed / Glassdoor: registra URL como "externo" para aplicação manual
- Anti-bot: delays aleatórios (3–6s entre vagas), movimento de mouse simulado, limite de 12 vagas/execução
- headless controlado por env var PLAYWRIGHT_HEADLESS (false local / true Railway)
- Credenciais em credentials.json ou env vars LINKEDIN_EMAIL, LINKEDIN_SENHA, GUPY_EMAIL, GUPY_SENHA
- Output: relatorio_aplicacoes.json + status atualizado no banco

### Módulo 6 — Scheduler + API (scheduler.py) ✅
- APScheduler (AsyncIOScheduler) executando pipeline a cada N horas (do config.json)
- FastAPI endpoints:
  - GET  /status   → estatísticas do banco + próximo ciclo
  - POST /config   → salva config.json e reagenda
  - POST /rodar    → dispara pipeline manualmente
  - GET  /vagas    → lista vagas com filtros (status, plataforma, limit)
  - POST /aplicar  → dispara aplicador nas vagas_para_aplicar.json
- Credenciais via arquivo ou env vars (EMAIL_REMETENTE, SENHA_APP, etc.)
- Procfile + railway.json para deploy Railway
- Logs estruturados com logging padrão Python

## Arquivos sensíveis (NUNCA no git)
- email_config.json   (credenciais Gmail)
- credentials.json    (login LinkedIn/Gupy — criado no Módulo 5)
- job_agent.db        (banco com dados pessoais)
- vagas_*.json        (dados temporários)

## Como rodar localmente
```bash
pip install -r requirements.txt
playwright install chromium
python scraper.py          # Módulo 2
python filtro_banco.py     # Módulo 3
python notificacao.py      # Módulo 4
python scheduler.py        # Módulo 6 (roda tudo junto)
```

## Dependências (requirements.txt)
```
playwright==1.44.0
apscheduler==3.10.4
fastapi==0.111.0
uvicorn==0.30.1
```
