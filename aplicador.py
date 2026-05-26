"""
JobAgent — Módulo 5: Aplicador
- Lê vagas aprovadas do Módulo 4
- LinkedIn Easy Apply: login + formulário multi-step
- Gupy: candidatura nativa (pula redirecionamentos externos)
- Indeed / Glassdoor: registra URL para aplicação manual
- Atualiza status no banco após cada ação
"""

import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext

from filtro_banco import inicializar_banco, atualizar_status


# ─────────────────────────────────────────
# CREDENCIAIS
# ─────────────────────────────────────────

def carregar_credenciais(path: str = "credentials.json") -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️  credentials.json não encontrado.")
        print("    Crie o arquivo com o seguinte formato:")
        print("""
    {
      "linkedin_email": "seu@email.com",
      "linkedin_senha": "suasenha",
      "gupy_email": "seu@email.com",
      "gupy_senha": "suasenha"
    }
        """)
        # Tenta variáveis de ambiente (Railway)
        return {
            "linkedin_email": os.environ.get("LINKEDIN_EMAIL", ""),
            "linkedin_senha": os.environ.get("LINKEDIN_SENHA", ""),
            "gupy_email":     os.environ.get("GUPY_EMAIL", ""),
            "gupy_senha":     os.environ.get("GUPY_SENHA", ""),
        }


# ─────────────────────────────────────────
# UTILITÁRIOS ANTI-BOT
# ─────────────────────────────────────────

async def _delay(min_s: float = 1.5, max_s: float = 3.5):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _mover_mouse(page: Page):
    await page.mouse.move(random.randint(100, 900), random.randint(100, 600))
    await asyncio.sleep(random.uniform(0.1, 0.3))


async def _digitar(page: Page, selector: str, texto: str):
    """Digita com velocidade humana."""
    await page.click(selector)
    for char in texto:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.13))


# ─────────────────────────────────────────
# LINKEDIN EASY APPLY
# ─────────────────────────────────────────

async def _login_linkedin(page: Page, credenciais: dict) -> bool:
    email = credenciais.get("linkedin_email", "")
    senha = credenciais.get("linkedin_senha", "")
    if not email or not senha:
        print("  [LinkedIn] Credenciais não configuradas — pulando login.")
        return False

    try:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await _delay(2, 4)

        await _digitar(page, "#username", email)
        await _delay(0.5, 1.5)
        await _digitar(page, "#password", senha)
        await _delay(0.5, 1.0)

        await page.click('[data-litms-control-urn="login-submit"], button[type="submit"]')
        await page.wait_for_url("**/feed/**", timeout=15000)
        await _delay(2, 4)

        print("  [LinkedIn] Login realizado.")
        return True

    except Exception as e:
        print(f"  [LinkedIn] Erro no login: {e}")
        return False


async def _aplicar_linkedin(page: Page, vaga: dict) -> dict:
    titulo = vaga.get("titulo", "")
    resultado = {
        "hash_id":    vaga.get("hash_id"),
        "plataforma": "LinkedIn",
        "titulo":     titulo,
        "url":        vaga.get("url", ""),
        "status":     "erro",
        "motivo":     "",
    }

    try:
        await page.goto(vaga["url"], wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 4)
        await _mover_mouse(page)

        # Botão Easy Apply
        btn = await page.query_selector(
            'button.jobs-apply-button, '
            '.jobs-s-apply button'
        )
        if not btn:
            resultado["status"] = "externo"
            resultado["motivo"] = "Sem botão Easy Apply"
            return resultado

        btn_text = (await btn.inner_text()).strip()
        if "Easy Apply" not in btn_text and "Candidatura simplificada" not in btn_text:
            resultado["status"] = "externo"
            resultado["motivo"] = f"Botão não é Easy Apply: '{btn_text}'"
            return resultado

        await btn.click()
        await _delay(2, 3)

        # Formulário multi-step — até 6 etapas
        for _ in range(6):
            await _mover_mouse(page)

            # Verifica confirmação de envio
            if await page.query_selector(
                '.artdeco-inline-feedback--success, '
                '[data-test-modal-id="easy-apply-success-modal"]'
            ):
                resultado["status"] = "aplicada"
                print(f"  [LinkedIn] ✅ {titulo}")
                return resultado

            # Botão Submeter
            submit = await page.query_selector(
                'button[aria-label="Enviar candidatura"], '
                'button[aria-label="Submit application"]'
            )
            if submit:
                await submit.click()
                await _delay(2, 4)
                resultado["status"] = "aplicada"
                print(f"  [LinkedIn] ✅ {titulo}")
                return resultado

            # Botão Próximo / Continuar
            prox = await page.query_selector(
                'button[aria-label="Continuar para a próxima etapa"], '
                'button[aria-label="Continue to next step"], '
                'footer button.artdeco-button--primary'
            )
            if prox:
                await prox.click()
                await _delay(1.5, 3)
            else:
                break

        # Checagem final
        if await page.query_selector('.artdeco-inline-feedback--success'):
            resultado["status"] = "aplicada"
        else:
            resultado["motivo"] = "Formulário multi-step não concluído"

    except Exception as e:
        resultado["motivo"] = str(e)
        print(f"  [LinkedIn] ❌ Erro em '{titulo}': {e}")

    return resultado


# ─────────────────────────────────────────
# GUPY
# ─────────────────────────────────────────

async def _aplicar_gupy(page: Page, vaga: dict) -> dict:
    titulo = vaga.get("titulo", "")
    resultado = {
        "hash_id":    vaga.get("hash_id"),
        "plataforma": "Gupy",
        "titulo":     titulo,
        "url":        vaga.get("url", ""),
        "status":     "erro",
        "motivo":     "",
    }

    try:
        await page.goto(vaga["url"], wait_until="domcontentloaded", timeout=30000)
        await _delay(2, 3)

        # Redireccionou para fora do Gupy?
        if "gupy.io" not in page.url:
            resultado["status"] = "externo"
            resultado["motivo"] = f"Redirecionou para: {page.url}"
            return resultado

        # Botão candidatar
        btn = await page.query_selector(
            'button[data-testid="apply-button"], '
            'button:has-text("Candidatar-se"), '
            'a:has-text("Candidatar-se")'
        )
        if not btn:
            resultado["status"] = "externo"
            resultado["motivo"] = "Botão de candidatura não encontrado"
            return resultado

        await btn.click()
        await _delay(2, 4)

        # Pós-clique: ainda no Gupy?
        if "gupy.io" not in page.url:
            resultado["status"] = "externo"
            resultado["motivo"] = f"Redirecionou após clicar: {page.url}"
            return resultado

        # Formulário — até 5 etapas
        for _ in range(5):
            confirmado = await page.query_selector(
                '[class*="success"], [class*="confirmation"], '
                'h1:has-text("Candidatura enviada"), h2:has-text("enviada")'
            )
            if confirmado:
                resultado["status"] = "aplicada"
                print(f"  [Gupy] ✅ {titulo}")
                return resultado

            prox = await page.query_selector(
                'button[type="submit"], '
                'button:has-text("Próximo"), '
                'button:has-text("Continuar"), '
                'button:has-text("Enviar candidatura")'
            )
            if prox:
                await prox.click()
                await _delay(1.5, 3)
            else:
                break

        if await page.query_selector('[class*="success"], [class*="confirmation"]'):
            resultado["status"] = "aplicada"
            print(f"  [Gupy] ✅ {titulo}")
        else:
            resultado["motivo"] = "Formulário não concluído"

    except Exception as e:
        resultado["motivo"] = str(e)
        print(f"  [Gupy] ❌ Erro em '{titulo}': {e}")

    return resultado


# ─────────────────────────────────────────
# INDEED / GLASSDOOR (externo)
# ─────────────────────────────────────────

def _registrar_externo(vaga: dict) -> dict:
    """Indeed e Glassdoor redirecionam para o site da empresa — marca para aplicação manual."""
    return {
        "hash_id":    vaga.get("hash_id"),
        "plataforma": vaga.get("plataforma"),
        "titulo":     vaga.get("titulo"),
        "url":        vaga.get("url"),
        "status":     "externo",
        "motivo":     "Plataforma redireciona para site externo — aplicar manualmente",
    }


# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────

async def aplicar_vagas(vagas: list[dict], credenciais: dict, limite: int = 12) -> dict:
    """
    Aplica nas vagas respeitando o limite por execução (anti-ban LinkedIn).
    Retorna relatório com aplicadas / externas / erros.
    """
    print(f"\n🤖 Módulo 5 — Aplicador")
    print(f"   Vagas recebidas: {len(vagas)}  |  Limite por execução: {limite}")

    conn = inicializar_banco()
    resultados: dict[str, list] = {"aplicadas": [], "externas": [], "erros": []}
    lote = vagas[:limite]

    # headless=False localmente para reduzir detecção; use PLAYWRIGHT_HEADLESS=true no Railway
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "false").lower() == "true"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
        )
        page = await context.new_page()
        linkedin_logado = False

        for i, vaga in enumerate(lote, 1):
            plataforma = (vaga.get("plataforma") or "").lower()
            titulo = vaga.get("titulo", "sem título")
            print(f"\n  [{i}/{len(lote)}] {titulo} · {plataforma.capitalize()}")

            try:
                if plataforma == "linkedin":
                    if not linkedin_logado:
                        linkedin_logado = await _login_linkedin(page, credenciais)
                        if not linkedin_logado:
                            resultados["erros"].append({
                                **_stub(vaga), "status": "erro", "motivo": "Falha no login LinkedIn"
                            })
                            continue
                    resultado = await _aplicar_linkedin(page, vaga)

                elif plataforma == "gupy":
                    resultado = await _aplicar_gupy(page, vaga)

                else:  # indeed, glassdoor, demais
                    resultado = _registrar_externo(vaga)

                # Persiste status no banco
                hash_id = vaga.get("hash_id")
                if hash_id:
                    if resultado["status"] == "aplicada":
                        atualizar_status(conn, hash_id, "aplicada")
                        resultados["aplicadas"].append(resultado)
                    elif resultado["status"] == "externo":
                        # Mantém "nova" — o usuário vai aplicar manualmente
                        resultados["externas"].append(resultado)
                    else:
                        resultados["erros"].append(resultado)

            except Exception as e:
                print(f"  ❌ Erro inesperado: {e}")
                resultados["erros"].append({**_stub(vaga), "status": "erro", "motivo": str(e)})

            if i < len(lote):
                await _delay(3, 6)  # pausa entre candidaturas

        await browser.close()

    conn.close()

    print(f"\n📊 Relatório de Aplicações:")
    print(f"   ✅ Aplicadas:         {len(resultados['aplicadas'])}")
    print(f"   🔗 Externas (manual): {len(resultados['externas'])}")
    print(f"   ❌ Erros:             {len(resultados['erros'])}")

    if resultados["externas"]:
        print(f"\n🔗 Aplicar manualmente:")
        for v in resultados["externas"]:
            print(f"   [{v['plataforma']}] {v['titulo']}")
            print(f"   → {v.get('url', '')}")

    relatorio = {
        "data":              datetime.now().isoformat(),
        "total_processadas": len(lote),
        **resultados,
    }
    with open("relatorio_aplicacoes.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Relatório salvo em relatorio_aplicacoes.json → pipeline concluído")
    return relatorio


def _stub(vaga: dict) -> dict:
    return {"hash_id": vaga.get("hash_id"), "plataforma": vaga.get("plataforma"),
            "titulo": vaga.get("titulo"), "url": vaga.get("url")}


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

def main():
    try:
        with open("vagas_para_aplicar.json", encoding="utf-8") as f:
            vagas = json.load(f)
    except FileNotFoundError:
        print("❌ vagas_para_aplicar.json não encontrado. Rode o Módulo 4 primeiro.")
        return

    if not vagas:
        print("ℹ️  Nenhuma vaga para aplicar.")
        return

    credenciais = carregar_credenciais()
    asyncio.run(aplicar_vagas(vagas, credenciais))


if __name__ == "__main__":
    main()
