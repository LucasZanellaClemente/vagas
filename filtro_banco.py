"""
JobAgent — Módulo 3: Filtro & Banco
- Recebe vagas do scraper
- Deduplica via SQLite
- Aplica filtros avançados
- Persiste histórico completo
"""

import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


# ─────────────────────────────────────────
# MODELO (espelho do scraper.py)
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
    descricao: Optional[str] = None
    data_coleta: str = ""
    status: str = "nova"          # nova | aprovada | ignorada | aplicada
    hash_id: str = ""

    def __post_init__(self):
        if not self.data_coleta:
            self.data_coleta = datetime.now().isoformat()
        if not self.hash_id:
            self.hash_id = gerar_hash(self)

    def to_dict(self):
        return asdict(self)


def gerar_hash(vaga: Vaga) -> str:
    """
    Gera um ID único por vaga baseado em título + empresa + plataforma.
    Evita duplicatas mesmo que a URL mude entre buscas.
    """
    chave = f"{vaga.titulo.lower().strip()}{vaga.empresa.lower().strip()}{vaga.plataforma.lower()}"
    return hashlib.md5(chave.encode()).hexdigest()


# ─────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────

DB_PATH = Path("job_agent.db")


def inicializar_banco() -> sqlite3.Connection:
    """Cria as tabelas se não existirem."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # retorna dicts
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS vagas (
            hash_id       TEXT PRIMARY KEY,
            titulo        TEXT NOT NULL,
            empresa       TEXT,
            localizacao   TEXT,
            salario       TEXT,
            nivel         TEXT,
            modalidade    TEXT,
            plataforma    TEXT,
            url           TEXT,
            descricao     TEXT,
            status        TEXT DEFAULT 'nova',
            data_coleta   TEXT,
            data_update   TEXT
        );

        CREATE TABLE IF NOT EXISTS execucoes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            data_inicio   TEXT,
            data_fim      TEXT,
            total_coletadas INTEGER DEFAULT 0,
            total_novas     INTEGER DEFAULT 0,
            total_duplicatas INTEGER DEFAULT 0,
            total_filtradas  INTEGER DEFAULT 0,
            plataformas   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_status    ON vagas(status);
        CREATE INDEX IF NOT EXISTS idx_plataforma ON vagas(plataforma);
        CREATE INDEX IF NOT EXISTS idx_data       ON vagas(data_coleta);
    """)

    conn.commit()
    return conn


# ─────────────────────────────────────────
# OPERAÇÕES NO BANCO
# ─────────────────────────────────────────

def inserir_vaga(conn: sqlite3.Connection, vaga: Vaga) -> bool:
    """
    Tenta inserir a vaga. Retorna True se era nova, False se duplicata.
    """
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO vagas (
                hash_id, titulo, empresa, localizacao, salario,
                nivel, modalidade, plataforma, url, descricao,
                status, data_coleta, data_update
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vaga.hash_id,
            vaga.titulo,
            vaga.empresa,
            vaga.localizacao,
            vaga.salario,
            vaga.nivel,
            vaga.modalidade,
            vaga.plataforma,
            vaga.url,
            vaga.descricao,
            vaga.status,
            vaga.data_coleta,
            datetime.now().isoformat(),
        ))
        conn.commit()
        return True  # vaga nova
    except sqlite3.IntegrityError:
        return False  # duplicata (hash_id já existe)


def buscar_vagas(
    conn: sqlite3.Connection,
    status: Optional[str] = None,
    plataforma: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Consulta vagas com filtros opcionais."""
    cur = conn.cursor()
    query = "SELECT * FROM vagas WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if plataforma:
        query += " AND plataforma = ?"
        params.append(plataforma)

    query += " ORDER BY data_coleta DESC LIMIT ?"
    params.append(limit)

    cur.execute(query, params)
    return [dict(row) for row in cur.fetchall()]


def atualizar_status(conn: sqlite3.Connection, hash_id: str, novo_status: str):
    """Atualiza o status de uma vaga (nova → aprovada / ignorada / aplicada)."""
    conn.execute(
        "UPDATE vagas SET status = ?, data_update = ? WHERE hash_id = ?",
        (novo_status, datetime.now().isoformat(), hash_id),
    )
    conn.commit()


def registrar_execucao(
    conn: sqlite3.Connection,
    data_inicio: str,
    total_coletadas: int,
    total_novas: int,
    total_duplicatas: int,
    total_filtradas: int,
    plataformas: list[str],
):
    conn.execute("""
        INSERT INTO execucoes (
            data_inicio, data_fim, total_coletadas,
            total_novas, total_duplicatas, total_filtradas, plataformas
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data_inicio,
        datetime.now().isoformat(),
        total_coletadas,
        total_novas,
        total_duplicatas,
        total_filtradas,
        json.dumps(plataformas),
    ))
    conn.commit()


def estatisticas(conn: sqlite3.Connection) -> dict:
    """Retorna um resumo do banco para exibir no dashboard."""
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM vagas")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vagas WHERE status = 'nova'")
    novas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vagas WHERE status = 'aplicada'")
    aplicadas = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vagas WHERE status = 'ignorada'")
    ignoradas = cur.fetchone()[0]

    cur.execute("SELECT plataforma, COUNT(*) as qtd FROM vagas GROUP BY plataforma")
    por_plataforma = {row[0]: row[1] for row in cur.fetchall()}

    cur.execute("SELECT COUNT(*) FROM execucoes")
    execucoes = cur.fetchone()[0]

    return {
        "total": total,
        "novas": novas,
        "aplicadas": aplicadas,
        "ignoradas": ignoradas,
        "por_plataforma": por_plataforma,
        "execucoes": execucoes,
    }


# ─────────────────────────────────────────
# FILTROS AVANÇADOS
# ─────────────────────────────────────────

def extrair_salario_numerico(texto: Optional[str]) -> Optional[int]:
    if not texto:
        return None
    import re
    nums = re.findall(r"[\d]+", texto.replace(".", "").replace(",", ""))
    for n in nums:
        val = int(n)
        if 500 <= val <= 50000:
            return val
    return None


def aplicar_filtros(vagas: list[Vaga], config: dict) -> tuple[list[Vaga], list[Vaga]]:
    """
    Separa vagas em (aprovadas, rejeitadas).
    Mais granular que o filtro básico do scraper — usado após deduplicação.
    """
    aprovadas, rejeitadas = [], []

    keywords = [k.lower() for k in config.get("keywords", [])]
    blacklist = [b.lower() for b in config.get("blacklist", [])]
    niveis_ok = [n.lower() for n in config.get("niveis", [])]
    modalidades_ok = [m.lower() for m in config.get("modalidades", [])]
    salario_min = config.get("salario_minimo", 0)

    for vaga in vagas:
        texto = f"{vaga.titulo} {vaga.descricao or ''}".lower()
        motivo = None

        # 1. Blacklist tem prioridade máxima
        hit_blacklist = next((b for b in blacklist if b in texto), None)
        if hit_blacklist:
            motivo = f"blacklist: '{hit_blacklist}'"

        # 2. Pelo menos uma keyword
        elif keywords and not any(k in texto for k in keywords):
            motivo = "nenhuma keyword encontrada"

        # 3. Nível (só filtra se o nível foi detectado)
        elif niveis_ok and vaga.nivel and vaga.nivel.lower() not in niveis_ok:
            motivo = f"nível '{vaga.nivel}' fora do perfil"

        # 4. Modalidade (só filtra se foi detectada)
        elif modalidades_ok and vaga.modalidade and vaga.modalidade.lower() not in modalidades_ok:
            motivo = f"modalidade '{vaga.modalidade}' fora do perfil"

        # 5. Salário mínimo (só filtra se salário foi informado)
        elif salario_min and vaga.salario:
            val = extrair_salario_numerico(vaga.salario)
            if val and val < salario_min:
                motivo = f"salário R$ {val} abaixo do mínimo R$ {salario_min}"

        if motivo:
            vaga.status = "ignorada"
            rejeitadas.append((vaga, motivo))
        else:
            vaga.status = "nova"
            aprovadas.append(vaga)

    return aprovadas, rejeitadas


# ─────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────

def processar_vagas(vagas_raw: list[dict], config: dict) -> dict:
    """
    Pipeline completo:
    1. Converte dicts → Vagas
    2. Deduplica via banco
    3. Aplica filtros avançados
    4. Persiste no SQLite
    5. Retorna relatório
    """
    inicio = datetime.now().isoformat()
    conn = inicializar_banco()

    print(f"\n📦 Módulo 3 — Banco & Filtro")
    print(f"   Vagas recebidas do scraper: {len(vagas_raw)}")

    # Converte para dataclasses
    vagas = []
    for d in vagas_raw:
        d.pop("hash_id", None)   # recalcula o hash sempre
        d.pop("status", None)
        vagas.append(Vaga(**{k: v for k, v in d.items() if k in Vaga.__dataclass_fields__}))

    # Deduplicação
    novas, duplicatas = [], []
    for vaga in vagas:
        if config.get("pular_duplicatas", True):
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM vagas WHERE hash_id = ?", (vaga.hash_id,))
            if cur.fetchone():
                duplicatas.append(vaga)
                continue
        novas.append(vaga)

    print(f"   Duplicatas ignoradas:       {len(duplicatas)}")
    print(f"   Vagas novas para filtrar:   {len(novas)}")

    # Filtros avançados
    aprovadas, rejeitadas = aplicar_filtros(novas, config)
    print(f"   Reprovadas pelos filtros:   {len(rejeitadas)}")
    print(f"   ✅ Aprovadas:               {len(aprovadas)}")

    # Persiste todas no banco (aprovadas + rejeitadas, com status correto)
    for vaga in aprovadas:
        inserir_vaga(conn, vaga)

    for vaga, _ in rejeitadas:
        inserir_vaga(conn, vaga)

    # Log de execução
    registrar_execucao(
        conn,
        data_inicio=inicio,
        total_coletadas=len(vagas_raw),
        total_novas=len(novas),
        total_duplicatas=len(duplicatas),
        total_filtradas=len(aprovadas),
        plataformas=list({v.plataforma for v in vagas}),
    )

    # Estatísticas finais
    stats = estatisticas(conn)
    conn.close()

    # Salva resultado para Módulo 4
    resultado = {
        "aprovadas": [v.to_dict() for v in aprovadas],
        "stats": stats,
    }
    with open("vagas_aprovadas.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Banco atualizado:")
    print(f"   Total histórico:  {stats['total']}")
    print(f"   Novas (pendentes): {stats['novas']}")
    print(f"   Aplicadas:         {stats['aplicadas']}")
    print(f"   Por plataforma:    {stats['por_plataforma']}")
    print(f"\n💾 Salvo em vagas_aprovadas.json → próximo: Módulo 4 (Email)")

    return resultado


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

def main():
    # Carrega config
    try:
        with open("config.json", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json não encontrado.")
        return

    # Carrega vagas do scraper
    try:
        with open("vagas_encontradas.json", encoding="utf-8") as f:
            vagas_raw = json.load(f)
    except FileNotFoundError:
        print("❌ vagas_encontradas.json não encontrado. Rode o Módulo 2 primeiro.")
        return

    processar_vagas(vagas_raw, config)


if __name__ == "__main__":
    main()
