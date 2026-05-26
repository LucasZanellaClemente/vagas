import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aplicador import carregar_credenciais as _cred_plataformas

async def aplicar_vagas(vagas, creds):
    from aplicador import main as _main
    await _main()
from filtro_banco import buscar_vagas, estatisticas, inicializar_banco, processar_vagas
from notificacao import carregar_credenciais as _cred_email
from notificacao import notificar
from scraper import carregar_config, rodar_scraper


# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("jobagent")


# ─────────────────────────────────────────
# CREDENCIAIS (arquivo ou variáveis de ambiente)
# ─────────────────────────────────────────

def get_cred_email() -> dict:
    cred = _cred_email()
    if not cred:
        cred = {
            "email_remetente":    os.environ.get("EMAIL_REMETENTE", ""),
            "senha_app":          os.environ.get("SENHA_APP", ""),
            "email_destinatario": os.environ.get("EMAIL_DESTINATARIO", ""),
        }
    return cred


def get_cred_plataformas() -> dict:
    cred = _cred_plataformas()
    if not cred.get("linkedin_email"):
        cred = {
            "linkedin_email": os.environ.get("LINKEDIN_EMAIL", ""),
            "linkedin_senha": os.environ.get("LINKEDIN_SENHA", ""),
            "gupy_email":     os.environ.get("GUPY_EMAIL", ""),
            "gupy_senha":     os.environ.get("GUPY_SENHA", ""),
        }
    return cred


# ─────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────

scheduler = AsyncIOScheduler()
_em_execucao = False


async def pipeline_completo():
    """Scraper → Filtro → Notificação (→ Aplicador se auto_aplicar)."""
    global _em_execucao
    if _em_execucao:
        log.warning("Execução anterior ainda em andamento — ciclo ignorado.")
        return

    _em_execucao = True
    inicio = datetime.now()
    log.info("▶ Iniciando pipeline")

    try:
        config = carregar_config()

        # Módulo 2 — Scraper
        log.info("🔍 Módulo 2 — Scraper")
        vagas_raw = await rodar_scraper(config)
        vagas_dicts = [v.to_dict() for v in vagas_raw]
        with open("vagas_encontradas.json", "w", encoding="utf-8") as f:
            json.dump(vagas_dicts, f, ensure_ascii=False, indent=2)

        # Módulo 3 — Filtro & Banco
        log.info("📦 Módulo 3 — Filtro & Banco")
        resultado = processar_vagas(vagas_dicts, config)
        aprovadas = resultado["aprovadas"]

        if not aprovadas:
            log.info("ℹ️  Nenhuma vaga aprovada neste ciclo.")
            return

        log.info(f"✅ {len(aprovadas)} vagas aprovadas")

        if config.get("auto_aplicar") and not config.get("notificar_antes"):
            # Aplica direto sem aguardar aprovação por email
            log.info(f"🤖 Módulo 5 — Aplicador automático ({len(aprovadas)} vagas)")
            await aplicar_vagas(aprovadas, get_cred_plataformas())
        else:
            # Módulo 4 — Notificação (envia email, não aguarda resposta aqui)
            log.info(f"📧 Módulo 4 — Notificação ({len(aprovadas)} vagas)")
            notificar(aprovadas, config, get_cred_email(), aguardar=False)

            # Persiste para aplicação manual via POST /aplicar
            with open("vagas_para_aplicar.json", "w", encoding="utf-8") as f:
                json.dump(aprovadas, f, ensure_ascii=False, indent=2)
            log.info("📩 Email enviado — aguardando resposta do usuário.")

    except Exception as e:
        log.error(f"❌ Erro no pipeline: {e}", exc_info=True)
    finally:
        duracao = (datetime.now() - inicio).seconds
        log.info(f"⏱️  Pipeline finalizado em {duracao}s")
        _em_execucao = False


def _reconfigurar_scheduler(frequencia_horas: int):
    scheduler.remove_all_jobs()
    scheduler.add_job(
        pipeline_completo,
        trigger=IntervalTrigger(hours=frequencia_horas),
        id="pipeline",
        name="Pipeline completo",
        replace_existing=True,
        misfire_grace_time=300,
    )
    log.info(f"⏱️  Agendador configurado: a cada {frequencia_horas}h")


# ─────────────────────────────────────────
# FASTAPI
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = carregar_config()
    _reconfigurar_scheduler(config.get("frequencia_horas", 2))
    scheduler.start()
    log.info("🚀 JobAgent API iniciada")
    yield
    scheduler.shutdown(wait=False)
    log.info("🛑 JobAgent encerrado")


app = FastAPI(title="JobAgent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfigPayload(BaseModel):
    keywords:         list[str] = []
    blacklist:        list[str] = []
    niveis:           list[str] = []
    modalidades:      list[str] = []
    salario_minimo:   int = 1500
    localizacao:      str = "São Paulo, SP"
    plataformas:      list[str] = []
    email:            str = ""
    frequencia_horas: int = 2
    auto_aplicar:     bool = False
    notificar_antes:  bool = True
    pular_duplicatas: bool = True
    salvar_log:       bool = True


# ── GET /status ──────────────────────────

@app.get("/status")
async def get_status():
    """Estatísticas do banco + estado do agendador."""
    try:
        conn = inicializar_banco()
        stats = estatisticas(conn)
        conn.close()

        job = scheduler.get_job("pipeline")
        proximo_run = job.next_run_time.isoformat() if job and job.next_run_time else None

        return {
            "status":       "running",
            "em_execucao":  _em_execucao,
            "proximo_ciclo": proximo_run,
            "banco":        stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /config ──────────────────────────

@app.post("/config")
async def post_config(payload: ConfigPayload):
    """Salva configuração do dashboard e reagenda o scheduler."""
    try:
        config = payload.model_dump()
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        _reconfigurar_scheduler(config["frequencia_horas"])
        log.info(f"⚙️  Config atualizada — frequência: {config['frequencia_horas']}h")
        return {"ok": True, "mensagem": "Configuração salva."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /rodar ──────────────────────────

@app.post("/rodar")
async def post_rodar():
    """Dispara o pipeline completo manualmente."""
    if _em_execucao:
        raise HTTPException(status_code=409, detail="Execução já em andamento.")
    asyncio.create_task(pipeline_completo())
    return {"ok": True, "mensagem": "Pipeline iniciado em background."}


# ── GET /vagas ───────────────────────────

@app.get("/vagas")
async def get_vagas(
    status:     Optional[str] = Query(None, description="nova | aprovada | aplicada | ignorada"),
    plataforma: Optional[str] = Query(None),
    limit:      int           = Query(50, le=500),
):
    """Lista vagas do banco com filtros opcionais."""
    try:
        conn = inicializar_banco()
        vagas = buscar_vagas(conn, status=status, plataforma=plataforma, limit=limit)
        conn.close()
        return {"total": len(vagas), "vagas": vagas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── POST /aplicar ─────────────────────────

@app.post("/aplicar")
async def post_aplicar():
    """Dispara o aplicador nas vagas de vagas_para_aplicar.json."""
    path = Path("vagas_para_aplicar.json")
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="vagas_para_aplicar.json não encontrado. Rode /rodar primeiro.",
        )
    try:
        with open(path, encoding="utf-8") as f:
            vagas = json.load(f)
        if not vagas:
            return {"ok": True, "mensagem": "Nenhuma vaga pendente."}
        asyncio.create_task(aplicar_vagas(vagas, get_cred_plataformas()))
        return {"ok": True, "mensagem": f"{len(vagas)} vaga(s) enfileiradas para aplicação."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("scheduler:app", host="0.0.0.0", port=port, reload=False)
