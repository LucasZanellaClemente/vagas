"""
JobAgent — Módulo 2: Scraper
Raspa vagas do LinkedIn, Indeed, Catho e InfoJobs usando Playwright e RSS.
"""

import asyncio
import json
import re
import feedparser
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext


# ─────────────────────────────────────────
# MODELO DE DADOS
# ─────────────────────────────────────────

@dataclass
class Vaga:
    titulo: str
    empresa: str
    localizacao: str
    salario: Optional[str]
    nivel: Optional[str]
    modalidade: Optional[str]
    plataforma: str
    url: str
    descricao: Optional[str]
    data_coleta: str = ""

    def __post_init__(self):
        if not self.data_coleta:
            self.data_coleta = datetime.now().isoformat()

    def to_dict(self):
        return asdict(self)


# ─────────────────────────────────────────
# CONFIGURAÇÃO (vinda do dashboard)
# ─────────────────────────────────────────

def carregar_config(path: str = "config.json") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "keywords": ["Data Analyst", "Data Engineer", "Python"],
            "blacklist": ["Sênior", "PJ Obrigatório"],
            "niveis": ["Estágio", "Júnior"],
            "modalidades": ["Remoto", "Híbrido"],
            "salario_minimo": 1500,
            "localizacao": "São Paulo, SP",
            "plataformas": ["linkedin", "indeed", "catho", "infojobs"],
        }


# ─────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────

def extrair_salario(texto: str) -> Optional[int]:
    if not texto:
        return None
    numeros = re.findall(r"[\d\.]+", texto.replace(",", "."))
    for n in numeros:
        try:
            val = int(float(n.replace(".", "")))
            if 500 <= val <= 50000:
                return val
        except ValueError:
            continue
    return None


def detectar_nivel(titulo: str, descricao: str = "") -> Optional[str]:
    texto = (titulo + " " + descricao).lower()
    if any(p in texto for p in ["estágio", "estagio", "intern", "trainee"]):
        return "Estágio"
    if any(p in texto for p in ["júnior", "junior", "jr", "entry"]):
        return "Júnior"
    if any(p in texto for p in ["pleno", "mid", "mid-level"]):
        return "Pleno"
    if any(p in texto for p in ["sênior", "senior", "sr", "lead", "principal"]):
        return "Sênior"
    return None


def detectar_modalidade(texto: str) -> Optional[str]:
    texto = texto.lower()
    if "remoto" in texto or "remote" in texto:
        return "Remoto"
    if "híbrido" in texto or "hibrido" in texto or "hybrid" in texto:
        return "Híbrido"
    if "presencial" in texto or "on-site" in texto or "onsite" in texto:
        return "Presencial"
    return None


def vaga_passa_filtros(vaga: Vaga, config: dict) -> bool:
    titulo_desc = (vaga.titulo + " " + (vaga.descricao or "")).lower()

    for palavra in config.get("blacklist", []):
        if palavra.lower() in titulo_desc:
            return False

    keywords = config.get("keywords", [])
    if keywords and not any(k.lower() in titulo_desc for k in keywords):
        return False

    niveis_config = [n.lower() for n in config.get("niveis", [])]
    if niveis_config and vaga.nivel:
        if vaga.nivel.lower() not in niveis_config:
            return False

    salario_min = config.get("salario_minimo", 0)
    if salario_min and vaga.salario:
        val = extrair_salario(vaga.salario)
        if val and val < salario_min:
            return False

    modalidades_config = [m.lower() for m in config.get("modalidades", [])]
    if modalidades_config and vaga.modalidade:
        if vaga.modalidade.lower() not in modalidades_config:
            return False

    return True


# ─────────────────────────────────────────
# SCRAPERS POR PLATAFORMA
# ─────────────────────────────────────────

async def scrape_linkedin(page: Page, config: dict) -> list[Vaga]:
    vagas = []
    keyword = config["keywords"][0].replace(" ", "%20")
    localizacao = config.get("localizacao", "São Paulo").replace(" ", "%20")

    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={keyword}&location={localizacao}&f_TPR=r86400"
    )

    print(f"  [LinkedIn] Acessando: {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(3000)

    for _ in range(3):
        await page.keyboard.press("End")
        await page.wait_for_timeout(1500)

    cards = await page.query_selector_all(".job-search-card")
    print(f"  [LinkedIn] {len(cards)} cards encontrados")

    for card in cards[:40]:
        try:
            titulo_el = await card.query_selector(".base-search-card__title")
            empresa_el = await card.query_selector(".base-search-card__subtitle")
            local_el = await card.query_selector(".job-search-card__location")
            link_el = await card.query_selector("a.base-card__full-link")

            titulo = (await titulo_el.inner_text()).strip() if titulo_el else ""
            empresa = (await empresa_el.inner_text()).strip() if empresa_el else ""
            local = (await local_el.inner_text()).strip() if local_el else ""
            href = await link_el.get_attribute("href") if link_el else ""

            if not titulo:
                continue

            nivel = detectar_nivel(titulo)
            modalidade = detectar_modalidade(local + " " + titulo)

            vaga = Vaga(
                titulo=titulo,
                empresa=empresa,
                localizacao=local,
                salario=None,
                nivel=nivel,
                modalidade=modalidade,
                plataforma="LinkedIn",
                url=href or url,
                descricao=None,
            )
            vagas.append(vaga)

        except Exception as e:
            print(f"  [LinkedIn] Erro em card: {e}")
            continue

    return vagas


async def scrape_indeed(page: Page, config: dict) -> list[Vaga]:
    """Usa RSS público do Indeed."""
    vagas = []
    keyword = config["keywords"][0].replace(" ", "+")
    localizacao = config.get("localizacao", "São Paulo, SP").replace(" ", "+")

    rss_url = f"https://br.indeed.com/rss?q={keyword}&l={localizacao}"
    print(f"  [Indeed] Acessando RSS: {rss_url}")

    try:
        feed = feedparser.parse(rss_url)
        print(f"  [Indeed] {len(feed.entries)} vagas no RSS")

        for entry in feed.entries[:40]:
            titulo = entry.get("title", "")
            local = entry.get("location", "")
            href = entry.get("link", "")
            descricao = entry.get("summary", "")

            empresa = ""
            if " - " in titulo:
                partes = titulo.split(" - ")
                empresa = partes[-1].strip()
                titulo = partes[0].strip()

            nivel = detectar_nivel(titulo, descricao)
            modalidade = detectar_modalidade(local + " " + titulo + " " + descricao)

            vaga = Vaga(
                titulo=titulo,
                empresa=empresa,
                localizacao=local,
                salario=None,
                nivel=nivel,
                modalidade=modalidade,
                plataforma="Indeed",
                url=href,
                descricao=descricao[:300] if descricao else None,
            )
            vagas.append(vaga)

    except Exception as e:
        print(f"  [Indeed] Erro: {e}")

    return vagas


async def scrape_catho(page: Page, config: dict) -> list[Vaga]:
    """Raspa vagas da Catho via Playwright."""
    vagas = []
    keyword = config["keywords"][0].replace(" ", "-").lower()

    url = f"https://www.catho.com.br/vagas/{keyword}/sao-paulo/"

    print(f"  [Catho] Acessando: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        for _ in range(3):
            await page.keyboard.press("End")
            await page.wait_for_timeout(1500)

        cards = await page.query_selector_all('[data-testid="job-card"], .sc-fzoLsD, article')
        print(f"  [Catho] {len(cards)} cards encontrados")

        for card in cards[:40]:
            try:
                titulo_el = await card.query_selector('h2, [data-testid="job-title"]')
                empresa_el = await card.query_selector('[data-testid="job-company"], .company-name')
                local_el = await card.query_selector('[data-testid="job-location"], .location')
                salario_el = await card.query_selector('[data-testid="job-salary"], .salary')
                link_el = await card.query_selector("a")

                titulo = (await titulo_el.inner_text()).strip() if titulo_el else ""
                empresa = (await empresa_el.inner_text()).strip() if empresa_el else ""
                local = (await local_el.inner_text()).strip() if local_el else ""
                salario = (await salario_el.inner_text()).strip() if salario_el else None
                href = await link_el.get_attribute("href") if link_el else ""

                if not titulo:
                    continue

                nivel = detectar_nivel(titulo)
                modalidade = detectar_modalidade(local + " " + titulo)

                vaga = Vaga(
                    titulo=titulo,
                    empresa=empresa,
                    localizacao=local,
                    salario=salario,
                    nivel=nivel,
                    modalidade=modalidade,
                    plataforma="Catho",
                    url=f"https://www.catho.com.br{href}" if href.startswith("/") else href,
                    descricao=None,
                )
                vagas.append(vaga)

            except Exception as e:
                print(f"  [Catho] Erro em card: {e}")
                continue

    except Exception as e:
        print(f"  [Catho] Erro geral: {e}")

    return vagas


async def scrape_infojobs(page: Page, config: dict) -> list[Vaga]:
    vagas = []
    keyword = config["keywords"][0].replace(" ", "+")

    url = f"https://www.infojobs.com.br/vagas-de-{keyword.replace('+', '-').lower()}-em-sao-paulo.aspx"

    print(f"  [InfoJobs] Acessando: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        cards = await page.query_selector_all(".js_rowCard")
        print(f"  [InfoJobs] {len(cards)} cards encontrados")

        for card in cards[:40]:
            try:
                titulo_el = await card.query_selector("h2.js_vacancyTitle")
                empresa_el = await card.query_selector("a.text-body.text-decoration-none")
                local_el = await card.query_selector(".mb-8")
                link_el = await card.query_selector("a.text-decoration-none")

                titulo = (await titulo_el.inner_text()).strip() if titulo_el else ""
                empresa = (await empresa_el.inner_text()).strip() if empresa_el else ""
                local = (await local_el.inner_text()).strip() if local_el else ""
                href = await link_el.get_attribute("href") if link_el else ""

                if not titulo:
                    continue

                nivel = detectar_nivel(titulo)
                modalidade = detectar_modalidade(local + " " + titulo)

                vaga = Vaga(
                    titulo=titulo,
                    empresa=empresa,
                    localizacao=local,
                    salario=None,
                    nivel=nivel,
                    modalidade=modalidade,
                    plataforma="InfoJobs",
                    url=f"https://www.infojobs.com.br{href}" if href.startswith("/") else href,
                    descricao=None,
                )
                vagas.append(vaga)

            except Exception as e:
                print(f"  [InfoJobs] Erro em card: {e}")
                continue

    except Exception as e:
        print(f"  [InfoJobs] Erro geral: {e}")

    return vagas


# ─────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ─────────────────────────────────────────

async def rodar_scraper(config: dict) -> list[Vaga]:
    plataformas_ativas = config.get("plataformas", [])
    todas_vagas: list[Vaga] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
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

        scrapers = {
            "linkedin": scrape_linkedin,
            "indeed": scrape_indeed,
            "catho": scrape_catho,
            "infojobs": scrape_infojobs,
        }

        tasks = []
        for nome, fn in scrapers.items():
            if nome in plataformas_ativas:
                page = await context.new_page()
                tasks.append((nome, fn, page))

        for nome, fn, page in tasks:
            print(f"\n🔍 Raspando {nome.capitalize()}...")
            try:
                vagas = await fn(page, config)
                todas_vagas.extend(vagas)
                print(f"  ✅ {len(vagas)} vagas coletadas de {nome.capitalize()}")
            except Exception as e:
                print(f"  ❌ Erro em {nome}: {e}")
            finally:
                await page.close()

        await browser.close()

    print(f"\n📊 Total coletado: {len(todas_vagas)} vagas")
    vagas_filtradas = [v for v in todas_vagas if vaga_passa_filtros(v, config)]
    print(f"✅ Após filtros: {len(vagas_filtradas)} vagas compatíveis")

    return vagas_filtradas


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

async def main():
    config = carregar_config()
    print("🤖 JobAgent — Módulo 2: Scraper")
    print(f"📋 Keywords: {config['keywords']}")
    print(f"🏢 Plataformas: {config['plataformas']}")
    print(f"💰 Salário mínimo: R$ {config['salario_minimo']}")
    print("─" * 50)

    vagas = await rodar_scraper(config)

    print("\n─" * 50)
    print(f"🎯 RESULTADO FINAL: {len(vagas)} vagas passaram pelos filtros\n")

    for i, v in enumerate(vagas, 1):
        print(f"{i}. [{v.plataforma}] {v.titulo} — {v.empresa}")
        print(f"   📍 {v.localizacao}  |  💰 {v.salario or 'N/A'}  |  📈 {v.nivel or 'N/A'}")
        print(f"   🔗 {v.url[:80]}...")
        print()

    with open("vagas_encontradas.json", "w", encoding="utf-8") as f:
        json.dump([v.to_dict() for v in vagas], f, ensure_ascii=False, indent=2)

    print("💾 Salvo em vagas_encontradas.json → próximo: Módulo 3 (Banco + Deduplicação)")


if __name__ == "__main__":
    asyncio.run(main())