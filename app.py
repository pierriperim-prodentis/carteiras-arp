"""
Minha carteira — app das assessoras da ARP.

Cada assessora entra com e-mail e senha (login do Supabase) e vê SÓ os
números dela: a trava fica no próprio banco (Row Level Security), não aqui.
Este código pode ser público: não tem nenhuma chave secreta.

Formulário "Registrar atendimento" (pensado para o celular): grava em
carteira_registros e o robô da Base copia para a aba INTERACOES da assessora.
No link de teste (…streamlit.app/?teste=1) grava com teste = true: não vai
para a planilha nem para o placar oficial.

"Lembrar neste aparelho": guarda no navegador só a chave de acesso do login
(refresh token, que muda a cada uso), nunca a senha. "Sair" apaga a chave.

Secrets (Streamlit Cloud > Settings > Secrets):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "sb_publishable_..."     # chave PÚBLICA (nunca a secreta)
"""

import os
import unicodedata

import requests
import streamlit as st
import streamlit.components.v1 as components

import carteiras_dados as cd

st.set_page_config(page_title="Minha carteira — ARP", page_icon="🦷", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stToolbar"]{visibility:hidden;height:0}
section[data-testid="stMain"], [data-testid="stAppViewContainer"]{background:#F5F3FA !important}
[data-testid="stMainBlockContainer"]{padding:0 !important;max-width:100% !important;width:100% !important}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{gap:0 !important}
/* menu lateral fixo e estreito: sem botão de encolher (o de reabrir ficava no cabeçalho escondido) */
section[data-testid="stSidebar"], section[data-testid="stSidebar"][aria-expanded="false"]{
  width:210px !important;min-width:210px !important;max-width:210px !important;
  transform:none !important;margin-left:0 !important;visibility:visible !important;display:flex !important}
[data-testid="stSidebarContent"]{width:210px !important;min-width:210px !important;transform:none !important;opacity:1 !important;visibility:visible !important}
[data-testid="stSidebarUserContent"]{width:100% !important}
[data-testid="stSidebarResizeHandle"]{display:none !important}
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarHeader"]{display:none !important}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:24px 12px !important;box-sizing:border-box}
[data-testid="stSidebarContent"]{padding:0 !important;overflow-x:hidden !important}
section[data-testid="stSidebar"] a{font-size:11.5px;overflow-wrap:anywhere}
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] button{font-size:13px !important}
/* abas e "Minha conta" do celular */
.st-key-abas, .st-key-conta_cel{padding:10px 14px !important}
.st-key-conta_cel{display:none !important}
iframe[title*="lembrar"]{display:block}
@media (max-width: 700px){
  section[data-testid="stSidebar"]{display:none !important}
  .st-key-conta_cel{display:block !important}
  .st-key-login{padding:20px 16px !important}
}
.st-key-login{padding:28px 32px;max-width:460px}
</style>""", unsafe_allow_html=True)

URL = str(st.secrets.get("SUPABASE_URL", "")).rstrip("/")
CHAVE = str(st.secrets.get("SUPABASE_ANON_KEY", "")).strip()
TIMEOUT = 20


def _h(token=None):
    h = {"apikey": CHAVE, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def entrar(email, senha):
    r = requests.post(f"{URL}/auth/v1/token", params={"grant_type": "password"}, headers=_h(),
                      json={"email": email.strip().lower(), "password": senha}, timeout=TIMEOUT)
    return r.json() if r.status_code == 200 else None


def renovar(refresh):
    r = requests.post(f"{URL}/auth/v1/token", params={"grant_type": "refresh_token"}, headers=_h(),
                      json={"refresh_token": refresh}, timeout=TIMEOUT)
    return r.json() if r.status_code == 200 else None


def ler(tabela, token, filtros=None):
    """Lê a tabela em páginas de 1000 (o banco devolve no máximo 1000 linhas por vez)."""
    linhas, inicio = [], 0
    while True:
        p = {"select": "*", **(filtros or {}), "limit": 1000, "offset": inicio}
        r = requests.get(f"{URL}/rest/v1/{tabela}", headers=_h(token), params=p, timeout=TIMEOUT)
        if r.status_code == 401:
            raise PermissionError
        r.raise_for_status()
        pagina = r.json()
        linhas.extend(pagina)
        if len(pagina) < 1000:
            return linhas
        inicio += 1000


def trocar_senha(token, nova):
    r = requests.put(f"{URL}/auth/v1/user", headers=_h(token), json={"password": nova}, timeout=TIMEOUT)
    return r.status_code == 200




def gravar_registro(token, dados):
    r = requests.post(f"{URL}/rest/v1/carteira_registros", headers={**_h(token), "Prefer": "return=representation"},
                      json=dados, timeout=TIMEOUT)
    if r.status_code == 401:
        raise PermissionError
    if r.status_code >= 300:
        raise RuntimeError(r.text[:300])
    return r.json()[0]


PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "componentes")
_lembrar = components.declare_component("lembrar", path=os.path.join(PASTA, "lembrar"))
_registrar = components.declare_component("registrar", path=os.path.join(PASTA, "registrar"))


def chave(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.split())


TESTE = st.query_params.get("teste") == "1"

if not URL or not CHAVE:
    st.error("App sem configuração (SUPABASE_URL / SUPABASE_ANON_KEY nos Secrets).")
    st.stop()

sessao = st.session_state.get("sessao")

if not sessao:
    # 1) aparelho lembrado? entra direto com a chave guardada no navegador
    if st.session_state.get("saiu"):
        _lembrar(modo="apagar", valor="", key="lembrar", default=None)
        guardado = ""
    else:
        guardado = _lembrar(modo="ler", valor="", key="lembrar", default=None)
        if guardado is None:          # o navegador ainda não respondeu
            st.stop()
    if guardado:
        s = renovar(guardado)
        if s:
            st.session_state["sessao"] = s
            st.session_state["lembrar_ok"] = True
            st.rerun()
        st.session_state["saiu"] = True      # chave vencida: apaga e pede login
        st.rerun()
    # 2) login normal
    with st.container(key="login"):
        st.markdown("## 🦷 Minha carteira")
        st.caption("Entre com o seu e-mail da Pródentis e a senha que você recebeu.")
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            lembrar = st.checkbox("Lembrar neste aparelho", value=True,
                                  help="Não pede a senha de novo neste celular/computador até você tocar em Sair. Não use em aparelho de outra pessoa.")
            ok = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if ok:
            s = entrar(email, senha)
            if s:
                st.session_state["sessao"] = s
                st.session_state["lembrar_ok"] = lembrar
                st.session_state.pop("saiu", None)
                st.rerun()
            st.error("E-mail ou senha incorretos.")
    st.stop()


def token_atual():
    return st.session_state["sessao"]["access_token"]


def renovar_ou_sair():
    novo = renovar(st.session_state["sessao"].get("refresh_token", ""))
    if not novo:
        st.session_state.pop("sessao", None)
        st.session_state["saiu"] = True
        st.rerun()
    st.session_state["sessao"] = novo
    return novo["access_token"]


def carregar():
    tok = token_atual()
    try:
        eu = ler("carteira_usuarios", tok)
    except PermissionError:
        tok = renovar_ou_sair()
        eu = ler("carteira_usuarios", tok)
    if not eu:
        return None, tok
    tab = {
        "carteira_resumo": ler("carteira_resumo", tok),
        "carteira_placar_dia": ler("carteira_placar_dia", tok, {"data": f"gte.{cd.desde(45)}", "order": "data"}),
        "carteira_agenda_dia": ler("carteira_agenda_dia", tok, {"data": f"eq.{cd.hoje()}"}),
        "carteira_clientes": ler("carteira_clientes", tok, dict([cd.FILTRO_CLIENTES])),
        "carteira_interacoes": ler("carteira_interacoes", tok, {"valido": "eq.true"}),
    }
    return tab, tok


tab, token = carregar()

# mantém a chave guardada no aparelho sempre atualizada (ela muda a cada renovação)
_lembrar(modo="gravar" if st.session_state.get("lembrar_ok") else "apagar",
         valor=st.session_state["sessao"].get("refresh_token", "") if st.session_state.get("lembrar_ok") else "",
         key="lembrar", default=None)


def sair():
    st.session_state.pop("sessao", None)
    st.session_state["saiu"] = True
    st.rerun()


def painel_conta(sufixo):
    if st.button("🔄 Atualizar", key="atu" + sufixo):
        st.rerun()
    with st.expander("🔑 Trocar minha senha"):
        n1 = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", key="n1" + sufixo)
        n2 = st.text_input("Repita a nova senha", type="password", key="n2" + sufixo)
        if st.button("Salvar nova senha", key="sv" + sufixo):
            if len(n1) < 8 or n1 != n2:
                st.error("As senhas precisam ser iguais e ter 8 caracteres ou mais.")
            elif trocar_senha(token_atual(), n1):
                st.success("Senha trocada.")
            else:
                st.error("Não consegui trocar agora. Tente de novo.")
    if st.button("Sair", key="sair" + sufixo):
        sair()


email_eu = st.session_state["sessao"].get("user", {}).get("email", "")
with st.sidebar:
    st.caption(f"Conectada como  \n**{email_eu}**")
    painel_conta("_lat")

if tab is None:
    st.warning("Seu login ainda não está ligado a uma carteira. Fale com o Pi.")
    st.stop()

dados = cd.montar(tab, "assessora")
a = dados["assessores"][0] if dados["assessores"] else None

aba = "carteira"
if a:
    with st.container(key="abas"):
        esc = st.segmented_control("Tela", ["📝 Registrar", "📊 Minha carteira"], default="📝 Registrar",
                                   key="aba", label_visibility="collapsed")
    aba = "registrar" if esc != "📊 Minha carteira" else "carteira"

if aba == "registrar":
    hoje = cd.hoje()
    try:
        regs = ler("carteira_registros", token_atual(), {"data": f"eq.{hoje}"})
    except PermissionError:
        renovar_ou_sair()
        regs = ler("carteira_registros", token_atual(), {"data": f"eq.{hoje}"})
    clientes = [{"n": c["cliente"], "st": c.get("status"),
                 "ult": (c["ultima_compra"][5:7] + "/" + c["ultima_compra"][:4]) if c.get("ultima_compra") else None,
                 "sist": c.get("sist_implantes")} for c in a.get("clientes", [])]
    atendidos = {chave(r["cliente"]) for r in regs} | {chave(x["cliente"]) for x in a.get("agenda_hoje", []) if x.get("atendido")}
    agenda = [x["cliente"] for x in sorted(a.get("agenda_hoje", []), key=lambda x: x.get("posicao", 99))
              if chave(x["cliente"]) not in atendidos]
    na_agenda = {chave(x["cliente"]) for x in a.get("agenda_hoje", [])}
    for c in clientes:
        c["agenda"] = chave(c["n"]) in na_agenda
    ph = next((p for p in a.get("placar", []) if p.get("data") == hoje), {})
    pendentes = [r for r in regs if not r.get("copiado_em") and (TESTE or not r.get("teste"))]
    feitos = int(ph.get("atendimentos") or 0) + len(pendentes)

    resp = st.session_state.get("resposta")
    valor = _registrar(dados={"nome": f"Minha carteira — {a['nome']}", "clientes": clientes, "agenda": agenda,
                              "feitos": feitos, "meta": int(ph.get("meta") or 20), "teste": TESTE, "resposta": resp},
                       key="registrar", default=None)
    feitos_nonces = st.session_state.setdefault("nonces", set())
    if valor and valor.get("nonce") and valor["nonce"] not in feitos_nonces:
        feitos_nonces.add(valor["nonce"])
        r = dict(valor.get("registro") or {})
        oficiais = {chave(c["n"]): c["n"] for c in clientes}
        nome = " ".join(str(r.get("cliente", "")).split())
        if chave(nome) in oficiais:                     # digitou diferente, mas é cliente da carteira
            nome, r["cliente_novo"] = oficiais[chave(nome)], False
        campos = ("cliente_novo", "origem", "tipo", "resultado", "proximo_contato", "sist_implantes",
                  "concorrente", "motivo", "nivel_risco", "observacoes")
        linha = {k: r.get(k) for k in campos}
        linha.update(cliente=nome, teste=TESTE)
        try:
            try:
                novo = gravar_registro(token_atual(), linha)
            except PermissionError:
                renovar_ou_sair()
                novo = gravar_registro(token_atual(), linha)
            st.session_state["resposta"] = {"nonce": valor["nonce"], "ok": True, "registro": novo}
        except Exception:
            st.session_state["resposta"] = {"nonce": valor["nonce"], "ok": False,
                                            "erro": "Não consegui salvar agora. Confira a internet e tente de novo."}
        st.rerun()
else:
    cd.mostrar(dados)

with st.container(key="conta_cel"):
    with st.expander(f"👤 Minha conta · {email_eu}"):
        painel_conta("_cel")
