"""
carteiras_dados.py — monta os dados da tela Carteiras (carteiras.html).

Não depende do Streamlit: recebe as linhas das tabelas carteira_* (lidas com a
chave do menuarp, ou com o login da assessora no app dela) e devolve o JSON
que o HTML desenha. Usado pela página do menuarp e pelo app das assessoras.

A tela é um componente (pasta componentes/carteiras): recebe os dados e
informa a própria altura ao Streamlit, então a página tem uma rolagem só.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "componentes", "carteiras")
HTML = os.path.join(PASTA, "index.html")
ORDEM = ["Madê", "Bruna", "Luana", "Diego", "Francely", "Lizia", "Jarlene"]
NOMES = {1: "Bruna", 2: "Madê", 3: "Luana", 4: "Diego", 5: "Francely", 6: "Lizia", 7: "Jarlene"}
TABELAS = ("carteira_resumo", "carteira_placar_dia", "carteira_agenda_dia", "carteira_clientes", "carteira_interacoes")


def hoje() -> str:
    return datetime.now(TZ).date().isoformat()


def desde(dias: int = 45) -> str:
    return (datetime.now(TZ).date() - timedelta(days=dias)).isoformat()


def _n(x):
    return None if x is None else float(x)


NUMEROS = ("valor_risco", "media_ant", "media_atual", "var_acum", "ciclo", "outros_valor", "fabrica_ano",
           "media_2023", "media_2024", "acum_ant", "acum_atual", "meses_sem_compra")
CAMPOS_INTER = ("data", "cliente", "tipo", "resultado", "origem", "motivo", "concorrente", "nivel_risco",
                "proxima_acao", "apoio", "proximo_contato", "observacoes")
# clientes que vão para a tela (ficha e busca): quem comprou nos 2 anos, está em risco, na agenda ou tem sistema de implantes informado
FILTRO_CLIENTES = ("or", "(media_ant.gt.0,media_atual.gt.0,valor_risco.gt.0,prioridade.gt.0,sist_implantes.not.is.null)")


def _ficha(r: dict) -> dict:
    f = {k: v for k, v in r.items() if k not in ("assessor_id", "atualizado_em", "prioridade")}
    for k in NUMEROS:
        f[k] = _n(f.get(k))
    return {k: v for k, v in f.items() if v not in (None, "")}      # sem campos vazios: pacote mais leve


def montar(tab: dict[str, list[dict]], modo: str = "gestor") -> dict:
    """tab: {nome_da_tabela: linhas}. Devolve o dicionário que vai para o HTML."""
    dia = hoje()
    ids = sorted({r["assessor_id"] for t in TABELAS for r in tab.get(t, [])},
                 key=lambda i: ORDEM.index(NOMES[i]) if NOMES.get(i) in ORDEM else 99)
    atualizado = max((r.get("atualizado_em") or "" for r in tab.get("carteira_placar_dia", [])), default="") or None
    saida = {"modo": modo, "hoje": dia, "atualizado": atualizado, "assessores": []}
    for aid in ids:
        res = next((r for r in tab.get("carteira_resumo", []) if r["assessor_id"] == aid), None)
        if res:
            res = {k: (_n(v) if k in ("fat_ant", "fat_atual", "var_pct", "valor_risco", "fabrica_ano") else v)
                   for k, v in res.items()}
        placar = sorted((r for r in tab.get("carteira_placar_dia", []) if r["assessor_id"] == aid), key=lambda r: r["data"])
        inter = sorted((r for r in tab.get("carteira_interacoes", []) if r["assessor_id"] == aid and r.get("valido")),
                       key=lambda r: (r.get("data") or "", r["linha"]), reverse=True)
        atendidos_hoje = {r["cliente"] for r in inter if r.get("data") == dia}
        agenda = sorted((r for r in tab.get("carteira_agenda_dia", []) if r["assessor_id"] == aid and r["data"] == dia),
                        key=lambda r: r["posicao"])
        clientes = [r for r in tab.get("carteira_clientes", []) if r["assessor_id"] == aid]
        risco = sorted((r for r in clientes if (_n(r.get("valor_risco")) or 0) > 0),
                       key=lambda r: -(_n(r.get("valor_risco")) or 0))
        saida["assessores"].append({
            "id": aid, "nome": NOMES.get(aid, str(aid)), "resumo": res,
            "placar": [{k: r[k] for k in ("data", "meta", "atendimentos", "receptivos", "efetivos", "pedidos",
                                          "agenda_total", "agenda_atendidos")} for r in placar],
            "agenda_hoje": [{"posicao": r["posicao"], "cliente": r["cliente"], "motivo": r.get("motivo"),
                             "status": r.get("status"), "valor_risco": _n(r.get("valor_risco")),
                             "atendido": r["cliente"] in atendidos_hoje} for r in agenda],
            "risco": [r["cliente"] for r in risco[:40]],
            "clientes": [_ficha(r) for r in clientes],
            "interacoes": [{k: r.get(k) for k in CAMPOS_INTER} for r in inter[:600]],
        })
    return saida


def html(dados: dict) -> str:
    """Arquivo solto para teste: o index.html com os dados no lugar do exemplo."""
    with open(HTML, encoding="utf-8") as f:
        modelo = f.read()
    ini, fim = modelo.index("/*DADOS*/") + len("/*DADOS*/"), modelo.index("/*FIM*/")
    js = json.dumps(dados, ensure_ascii=False, default=str).replace("</", "<\\/")
    return modelo[:ini] + js + modelo[fim:]


_componente = None


def mostrar(dados: dict, key: str = "carteiras") -> None:
    """Desenha a tela no Streamlit (altura automática, sem rolagem própria)."""
    global _componente
    import streamlit.components.v1 as components
    if _componente is None:
        _componente = components.declare_component("carteiras", path=PASTA)
    _componente(dados=dados, key=key, default=None)
