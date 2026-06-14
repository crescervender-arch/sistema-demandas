# Sistema de Controle de Demandas Jurídicas

Plataforma web para gestão operacional e financeira de demandas jurídicas —
baseada na especificação técnica da **Crescer Tecnologia e Gestão**.

Um único servidor (FastAPI) com banco **SQL** serve a API e o frontend web. Todos
os usuários acessam pelo mesmo link e veem os **dados sempre atualizados** (banco
compartilhado).

## Funcionalidades

- **Login master** que configura todos os acessos, perfis e cadastros do sistema.
- **RBAC com 5 perfis**: `master` › `sócio` › `gestor` › `advogado` › `estagiário`.
- **Núcleos jurídicos**, **profissionais/usuários** e **demandas** com CRUD completo.
- **Ciclo de vida da demanda**: Triagem → Alocação → Execução → Encerrado → Arquivado,
  com **audit trail** (histórico imutável de movimentações).
- **Alocação de equipe** com verificação de carga máxima por profissional.
- **Indicadores de SLA** (prazo interno: ok / vencendo 48h / vencida).
- **Dashboard da controladoria** com KPIs: demandas ativas, encerradas no mês,
  aderência ao SLA, produção por núcleo, throughput 12 meses, aging, ranking de SLA
  e carteira financeira.

## Como rodar localmente (Windows)

Pré-requisito: **Python 3.11+** (já detectado: 3.14 via launcher `py`).

**Opção rápida** — pelo PowerShell, dentro da pasta do projeto:

```powershell
.\iniciar.ps1
```

**Manual:**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Acesse: **http://localhost:8000**

### Logins de demonstração

| Perfil | E-mail | Senha |
|--------|--------|-------|
| **Master** | master@bbz.adv.br | master123 |
| Sócio | socio@bbz.adv.br | socio123 |
| Gestor | gestor.trab@bbz.adv.br | gestor123 |
| Advogado | adv1@bbz.adv.br | adv123 |
| Estagiário | estag1@bbz.adv.br | estag123 |

> Os dados de exemplo são criados automaticamente na primeira execução.
> Para zerar o banco, apague o arquivo `demandas.db` e reinicie.

## Acesso por link na rede local

Outras pessoas na mesma rede (Wi-Fi do escritório) já podem acessar via:
`http://SEU_IP:8000` (descubra o IP com `ipconfig`). O servidor sobe em `0.0.0.0`.

## Publicar na internet (link público)

O projeto já está pronto para deploy (Railway, Render, etc.):

1. Suba a pasta para um repositório Git.
2. Em **Railway/Render**, crie um serviço a partir do repo (detecta o `Procfile`).
3. Defina as variáveis de ambiente:
   - `SECRET_KEY` — chave aleatória para assinar os tokens.
   - `DATABASE_URL` *(opcional)* — para usar **PostgreSQL** em produção, ex.:
     `postgresql+psycopg://user:senha@host:5432/demandas`.
     Sem essa variável, usa SQLite (arquivo local).

> **Importante:** em produção, prefira PostgreSQL — o SQLite é apagado a cada
> redeploy em hosts efêmeros. O código já suporta os dois sem alterações.

## Stack

- **Backend:** Python + FastAPI + SQLAlchemy 2 (SQLite por padrão, PostgreSQL opcional)
- **Frontend:** SPA em HTML/CSS/JS puro (sem build), servida pelo próprio backend
- **Auth:** token assinado (HMAC-SHA256) + senha com PBKDF2 (stdlib)

## Estrutura

```
main.py        API + rotas + RBAC + KPIs + serve o frontend
database.py    Conexão SQL (SQLite/PostgreSQL)
models.py      Tabelas (nucleos, usuarios, demandas, alocacoes, movimentacoes, eventos_sla)
auth.py        Hash de senha e tokens
schemas.py     Validação dos requests (Pydantic)
seed.py        Carga inicial (master + dados de exemplo)
static/        Frontend (index.html, styles.css, app.js)
```
