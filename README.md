# Minha carteira — ARP

App das assessoras: cada uma entra com e-mail e senha e vê só a própria carteira
(placar de atendimentos, agenda do dia, clientes em risco, vendas no ano).

- Os dados vêm do banco do menuarp (Supabase), gravados pelo robô das carteiras.
- A trava de "cada uma vê só o seu" fica no próprio banco (Row Level Security).
- Este repositório é público e não tem nenhuma chave secreta.
  Nos Secrets do Streamlit vão só `SUPABASE_URL` e `SUPABASE_ANON_KEY` (chave pública).
