"""
Minha carteira — app das assessoras da ARP.

Cada assessora entra com e-mail e senha (login do Supabase) e vê SÓ os
números dela: a trava fica no próprio banco (Row Level Security), não aqui.
Este código pode ser público: não tem nenhuma chave secreta.

Secrets (Streamlit Cloud > Settings > Secrets):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_ANON_KEY = "sb_publishable_..."     # chave PÚBLICA (nunca a secreta)
"""

import requests
import streamlit as st

import carteiras_dados as cd

st.set_page_config(page_title="Minha carteira — ARP", page_icon="🦷", layout="wide")
st.markdown("""<style>
#MainMenu, footer, [data-testid="stHeader"], [data-testid="stToolbar"]{visibility:hidden;height:0}
section[data-testid="stMain"], [data-testid="stAppViewContainer"]{background:#F5F3FA !important}
[data-testid="stMainBlockContainer"]{padding:0 !important;max-width:100% !important;width:100% !important}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{gap:0 !important}
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


if not URL or not CHAVE:
    st.error("App sem configuração (SUPABASE_URL / SUPABASE_ANON_KEY nos Secrets).")
    st.stop()

sessao = st.session_state.get("sessao")

if not sessao:
    st.markdown("## 🦷 Minha carteira")
    st.caption("Entre com o seu e-mail da Pródentis e a senha que você recebeu.")
    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar", type="primary")
    if ok:
        s = entrar(email, senha)
        if s:
            st.session_state["sessao"] = s
            st.rerun()
        st.error("E-mail ou senha incorretos.")
    st.stop()


def carregar():
    s = st.session_state["sessao"]
    tok = s["access_token"]
    try:
        eu = ler("carteira_usuarios", tok)
    except PermissionError:
        novo = renovar(s.get("refresh_token", ""))
        if not novo:
            st.session_state.pop("sessao", None)
            st.rerun()
        st.session_state["sessao"] = novo
        tok = novo["access_token"]
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
with st.sidebar:
    st.caption(f"Conectada como **{st.session_state['sessao'].get('user', {}).get('email', '')}**")
    if st.button("🔄 Atualizar"):
        st.rerun()
    with st.expander("🔑 Trocar minha senha"):
        n1 = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", key="n1")
        n2 = st.text_input("Repita a nova senha", type="password", key="n2")
        if st.button("Salvar nova senha"):
            if len(n1) < 8 or n1 != n2:
                st.error("As senhas precisam ser iguais e ter 8 caracteres ou mais.")
            elif trocar_senha(token, n1):
                st.success("Senha trocada.")
            else:
                st.error("Não consegui trocar agora. Tente de novo.")
    if st.button("Sair"):
        st.session_state.pop("sessao", None)
        st.rerun()

if tab is None:
    st.warning("Seu login ainda não está ligado a uma carteira. Fale com o Pi.")
    st.stop()

cd.mostrar(cd.montar(tab, "assessora"))
