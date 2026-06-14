"""Sistema de Controle de Demandas Jurídicas — API FastAPI + SQL.

Um único servidor: expõe a API REST em /api/* e serve o frontend web (pasta
static/) na raiz. Todos os usuários acessam o mesmo banco — dados sempre
atualizados e compartilhados.

Rodar:  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import Base, SessionLocal, engine, get_db
from seed import semear_dados

app = FastAPI(title="Sistema de Controle de Demandas Jurídicas", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATUS_FECHADOS = ("encerrado", "arquivado")
FLUXO_STATUS = {
    "triagem": ["alocacao", "arquivado"],
    "alocacao": ["execucao", "triagem", "arquivado"],
    "execucao": ["encerrado", "alocacao", "arquivado"],
    "encerrado": ["arquivado", "execucao"],
    "arquivado": ["triagem"],
}


# --------------------------------------------------------------------------- #
# Inicialização
# --------------------------------------------------------------------------- #
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        semear_dados(db)
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Autenticação / RBAC
# --------------------------------------------------------------------------- #
def usuario_atual(authorization: str = Header(None), db: Session = Depends(get_db)) -> models.Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Não autenticado")
    uid = auth.ler_token(authorization.split(" ", 1)[1])
    if not uid:
        raise HTTPException(401, "Sessão expirada. Faça login novamente.")
    u = db.get(models.Usuario, uid)
    if not u or not u.ativo:
        raise HTTPException(401, "Usuário inválido ou inativo")
    return u


def exigir(usuario: models.Usuario, minimo: str):
    if auth.nivel(usuario.perfil_acesso) < auth.nivel(minimo):
        raise HTTPException(403, "Acesso negado para o seu perfil")


# --------------------------------------------------------------------------- #
# Serialização
# --------------------------------------------------------------------------- #
def s_usuario(u: models.Usuario, db: Session = None) -> dict:
    d = {
        "id": u.id, "nome": u.nome, "email": u.email, "oab": u.oab,
        "cargo": u.cargo, "perfil_acesso": u.perfil_acesso,
        "nucleo_id": u.nucleo_id, "gestor_id": u.gestor_id,
        "carga_maxima": u.carga_maxima, "carga_atual": u.carga_atual,
        "celular": u.celular, "ativo": u.ativo,
        "criado_em": u.criado_em.isoformat() if u.criado_em else None,
    }
    if db is not None:
        nuc = db.get(models.Nucleo, u.nucleo_id) if u.nucleo_id else None
        d["nucleo_nome"] = nuc.nome if nuc else None
    return d


def s_nucleo(n: models.Nucleo, db: Session) -> dict:
    gestor = db.get(models.Usuario, n.gestor_id) if n.gestor_id else None
    total_prof = db.query(models.Usuario).filter(
        models.Usuario.nucleo_id == n.id, models.Usuario.ativo == True
    ).count()
    total_dem = db.query(models.Demanda).filter(models.Demanda.nucleo_id == n.id).count()
    return {
        "id": n.id, "nome": n.nome, "sigla": n.sigla, "gestor_id": n.gestor_id,
        "gestor_nome": gestor.nome if gestor else None, "ativo": n.ativo,
        "total_profissionais": total_prof, "total_demandas": total_dem,
        "criado_em": n.criado_em.isoformat() if n.criado_em else None,
    }


def s_demanda(d: models.Demanda, db: Session, completo: bool = False) -> dict:
    nuc = db.get(models.Nucleo, d.nucleo_id)
    resp = (
        db.query(models.Alocacao)
        .filter(models.Alocacao.demanda_id == d.id, models.Alocacao.responsavel_principal == True)
        .first()
    )
    resp_nome = None
    if resp:
        ru = db.get(models.Usuario, resp.profissional_id)
        resp_nome = ru.nome if ru else None
    dias_aberto = (date.today() - d.criado_em.date()).days if d.criado_em else 0
    sla = sla_status(d)
    out = {
        "id": d.id, "titulo": d.titulo, "descricao": d.descricao,
        "tipo_demanda": d.tipo_demanda, "status": d.status, "prioridade": d.prioridade,
        "nucleo_id": d.nucleo_id, "nucleo_nome": nuc.nome if nuc else None,
        "responsavel_nome": resp_nome,
        "valor_causa": float(d.valor_causa) if d.valor_causa is not None else None,
        "prazo_legal": d.prazo_legal.isoformat() if d.prazo_legal else None,
        "prazo_interno": d.prazo_interno.isoformat() if d.prazo_interno else None,
        "numero_processo": d.numero_processo, "tribunal": d.tribunal,
        "fase_processual": d.fase_processual, "dias_aberto": dias_aberto,
        "sla_status": sla,
        "criado_em": d.criado_em.isoformat() if d.criado_em else None,
        "atualizado_em": d.atualizado_em.isoformat() if d.atualizado_em else None,
        "proximos_status": FLUXO_STATUS.get(d.status, []),
    }
    if completo:
        alocs = db.query(models.Alocacao).filter(models.Alocacao.demanda_id == d.id).all()
        out["alocacoes"] = []
        for a in alocs:
            au = db.get(models.Usuario, a.profissional_id)
            out["alocacoes"].append({
                "id": a.id, "profissional_id": a.profissional_id,
                "profissional_nome": au.nome if au else None,
                "papel": a.papel, "responsavel_principal": a.responsavel_principal,
                "horas_estimadas": a.horas_estimadas, "horas_realizadas": a.horas_realizadas,
                "status": a.status,
            })
        movs = (
            db.query(models.Movimentacao)
            .filter(models.Movimentacao.demanda_id == d.id)
            .order_by(models.Movimentacao.ocorrido_em.desc())
            .all()
        )
        out["movimentacoes"] = []
        for m in movs:
            mu = db.get(models.Usuario, m.profissional_id)
            out["movimentacoes"].append({
                "status_anterior": m.status_anterior, "status_novo": m.status_novo,
                "observacao": m.observacao, "autor": mu.nome if mu else None,
                "ocorrido_em": m.ocorrido_em.isoformat() if m.ocorrido_em else None,
            })
    return out


def sla_status(d: models.Demanda) -> str:
    if d.status in STATUS_FECHADOS or not d.prazo_interno:
        return "ok"
    hoje = date.today()
    if d.prazo_interno < hoje:
        return "vencida"
    if d.prazo_interno <= hoje + timedelta(days=2):
        return "vencendo"
    return "ok"


# --------------------------------------------------------------------------- #
# AUTH
# --------------------------------------------------------------------------- #
@app.post("/api/auth/login")
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    u = db.query(models.Usuario).filter(models.Usuario.email == body.email.lower().strip()).first()
    if not u or not auth.verificar_senha(body.senha, u.senha_hash):
        raise HTTPException(401, "E-mail ou senha incorretos")
    if not u.ativo:
        raise HTTPException(403, "Usuário desativado. Procure o administrador.")
    return {"token": auth.criar_token(u.id), "usuario": s_usuario(u, db)}


@app.get("/api/auth/me")
def me(usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    return s_usuario(usuario, db)


@app.post("/api/auth/senha")
def trocar_senha(body: schemas.SenhaIn, usuario: models.Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    if body.senha_atual is not None and not auth.verificar_senha(body.senha_atual, usuario.senha_hash):
        raise HTTPException(400, "Senha atual incorreta")
    usuario.senha_hash = auth.hash_senha(body.nova_senha)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# USUÁRIOS / ACESSOS  (gerência: master e sócio)
# --------------------------------------------------------------------------- #
@app.get("/api/usuarios")
def listar_usuarios(usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    # Perfis operacionais conseguem listar para alocação; dados sensíveis ficam no detalhe.
    us = db.query(models.Usuario).order_by(models.Usuario.nome).all()
    return [s_usuario(u, db) for u in us]


@app.post("/api/usuarios")
def criar_usuario(body: schemas.UsuarioIn, usuario: models.Usuario = Depends(usuario_atual),
                  db: Session = Depends(get_db)):
    exigir(usuario, "socio")
    if not body.senha:
        raise HTTPException(400, "Senha é obrigatória para novo usuário")
    if body.perfil_acesso not in auth.PERFIL_NIVEL:
        raise HTTPException(400, "Perfil de acesso inválido")
    email = body.email.lower().strip()
    if db.query(models.Usuario).filter(models.Usuario.email == email).first():
        raise HTTPException(409, "Já existe um usuário com este e-mail")
    u = models.Usuario(
        nome=body.nome, email=email, senha_hash=auth.hash_senha(body.senha),
        cargo=body.cargo, oab=body.oab, celular=body.celular,
        perfil_acesso=body.perfil_acesso, nucleo_id=body.nucleo_id or None,
        gestor_id=body.gestor_id or None, carga_maxima=body.carga_maxima, ativo=body.ativo,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return s_usuario(u, db)


@app.put("/api/usuarios/{uid}")
def editar_usuario(uid: str, body: schemas.UsuarioIn,
                   usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    exigir(usuario, "socio")
    u = db.get(models.Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuário não encontrado")
    email = body.email.lower().strip()
    outro = db.query(models.Usuario).filter(models.Usuario.email == email, models.Usuario.id != uid).first()
    if outro:
        raise HTTPException(409, "E-mail já usado por outro usuário")
    u.nome, u.email, u.cargo, u.oab = body.nome, email, body.cargo, body.oab
    u.celular, u.perfil_acesso = body.celular, body.perfil_acesso
    u.nucleo_id, u.gestor_id = body.nucleo_id or None, body.gestor_id or None
    u.carga_maxima, u.ativo = body.carga_maxima, body.ativo
    if body.senha:
        u.senha_hash = auth.hash_senha(body.senha)
    db.commit()
    db.refresh(u)
    return s_usuario(u, db)


@app.delete("/api/usuarios/{uid}")
def desativar_usuario(uid: str, usuario: models.Usuario = Depends(usuario_atual),
                      db: Session = Depends(get_db)):
    exigir(usuario, "socio")
    u = db.get(models.Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuário não encontrado")
    if u.id == usuario.id:
        raise HTTPException(400, "Você não pode desativar a si mesmo")
    if u.perfil_acesso == "master":
        raise HTTPException(400, "O usuário master não pode ser desativado")
    u.ativo = False           # soft-delete (campo ativo)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# NÚCLEOS  (gerência: sócio/master)
# --------------------------------------------------------------------------- #
@app.get("/api/nucleos")
def listar_nucleos(usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    ns = db.query(models.Nucleo).order_by(models.Nucleo.nome).all()
    return [s_nucleo(n, db) for n in ns]


@app.post("/api/nucleos")
def criar_nucleo(body: schemas.NucleoIn, usuario: models.Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    exigir(usuario, "socio")
    sigla = body.sigla.upper().strip()
    if db.query(models.Nucleo).filter(models.Nucleo.sigla == sigla).first():
        raise HTTPException(409, "Já existe um núcleo com esta sigla")
    n = models.Nucleo(nome=body.nome, sigla=sigla, gestor_id=body.gestor_id or None, ativo=body.ativo)
    db.add(n)
    db.commit()
    db.refresh(n)
    return s_nucleo(n, db)


@app.put("/api/nucleos/{nid}")
def editar_nucleo(nid: str, body: schemas.NucleoIn, usuario: models.Usuario = Depends(usuario_atual),
                  db: Session = Depends(get_db)):
    exigir(usuario, "socio")
    n = db.get(models.Nucleo, nid)
    if not n:
        raise HTTPException(404, "Núcleo não encontrado")
    sigla = body.sigla.upper().strip()
    outro = db.query(models.Nucleo).filter(models.Nucleo.sigla == sigla, models.Nucleo.id != nid).first()
    if outro:
        raise HTTPException(409, "Sigla já usada por outro núcleo")
    n.nome, n.sigla, n.gestor_id, n.ativo = body.nome, sigla, body.gestor_id or None, body.ativo
    db.commit()
    db.refresh(n)
    return s_nucleo(n, db)


# --------------------------------------------------------------------------- #
# DEMANDAS
# --------------------------------------------------------------------------- #
def demandas_visiveis(usuario: models.Usuario, db: Session):
    q = db.query(models.Demanda)
    perfil = usuario.perfil_acesso
    if perfil in ("master", "socio"):
        return q
    if perfil == "gestor":
        return q.filter(models.Demanda.nucleo_id == usuario.nucleo_id)
    # advogado / estagiario: apenas demandas em que está alocado
    ids = [a.demanda_id for a in db.query(models.Alocacao.demanda_id)
           .filter(models.Alocacao.profissional_id == usuario.id).all()]
    return q.filter(models.Demanda.id.in_(ids or ["__none__"]))


@app.get("/api/demandas")
def listar_demandas(status: Optional[str] = None, nucleo_id: Optional[str] = None,
                    busca: Optional[str] = None,
                    usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    q = demandas_visiveis(usuario, db)
    if status:
        q = q.filter(models.Demanda.status == status)
    if nucleo_id:
        q = q.filter(models.Demanda.nucleo_id == nucleo_id)
    if busca:
        like = f"%{busca}%"
        q = q.filter(models.Demanda.titulo.ilike(like))
    demandas = q.order_by(models.Demanda.criado_em.desc()).all()
    return [s_demanda(d, db) for d in demandas]


@app.get("/api/demandas/{did}")
def obter_demanda(did: str, usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    d = db.get(models.Demanda, did)
    if not d:
        raise HTTPException(404, "Demanda não encontrada")
    return s_demanda(d, db, completo=True)


@app.post("/api/demandas")
def criar_demanda(body: schemas.DemandaIn, usuario: models.Usuario = Depends(usuario_atual),
                  db: Session = Depends(get_db)):
    exigir(usuario, "advogado")
    if not db.get(models.Nucleo, body.nucleo_id):
        raise HTTPException(400, "Núcleo inválido")
    d = models.Demanda(
        titulo=body.titulo, descricao=body.descricao, tipo_demanda=body.tipo_demanda,
        prioridade=body.prioridade, nucleo_id=body.nucleo_id, criado_por=usuario.id,
        valor_causa=body.valor_causa,
        prazo_legal=date.fromisoformat(body.prazo_legal) if body.prazo_legal else None,
        prazo_interno=date.fromisoformat(body.prazo_interno) if body.prazo_interno else None,
        numero_processo=body.numero_processo, tribunal=body.tribunal,
        fase_processual=body.fase_processual, status="triagem",
    )
    db.add(d)
    db.flush()
    db.add(models.Movimentacao(demanda_id=d.id, profissional_id=usuario.id,
                               status_anterior=None, status_novo="triagem",
                               observacao="Demanda criada"))
    db.commit()
    db.refresh(d)
    return s_demanda(d, db, completo=True)


@app.put("/api/demandas/{did}")
def editar_demanda(did: str, body: schemas.DemandaIn, usuario: models.Usuario = Depends(usuario_atual),
                   db: Session = Depends(get_db)):
    d = db.get(models.Demanda, did)
    if not d:
        raise HTTPException(404, "Demanda não encontrada")
    # advogado só edita as próprias; gestor o seu núcleo; sócio/master tudo
    if usuario.perfil_acesso == "advogado":
        aloc = db.query(models.Alocacao).filter(
            models.Alocacao.demanda_id == did, models.Alocacao.profissional_id == usuario.id,
            models.Alocacao.responsavel_principal == True).first()
        if not aloc:
            raise HTTPException(403, "Você só pode editar demandas em que é responsável")
    elif usuario.perfil_acesso == "gestor" and d.nucleo_id != usuario.nucleo_id:
        raise HTTPException(403, "Demanda fora do seu núcleo")
    elif usuario.perfil_acesso == "estagiario":
        raise HTTPException(403, "Estagiário não pode editar demandas")
    d.titulo, d.descricao, d.tipo_demanda = body.titulo, body.descricao, body.tipo_demanda
    d.prioridade, d.nucleo_id = body.prioridade, body.nucleo_id
    d.valor_causa = body.valor_causa
    d.prazo_legal = date.fromisoformat(body.prazo_legal) if body.prazo_legal else None
    d.prazo_interno = date.fromisoformat(body.prazo_interno) if body.prazo_interno else None
    d.numero_processo, d.tribunal, d.fase_processual = body.numero_processo, body.tribunal, body.fase_processual
    db.commit()
    db.refresh(d)
    return s_demanda(d, db, completo=True)


@app.post("/api/demandas/{did}/status")
def mudar_status(did: str, body: schemas.StatusIn, usuario: models.Usuario = Depends(usuario_atual),
                 db: Session = Depends(get_db)):
    d = db.get(models.Demanda, did)
    if not d:
        raise HTTPException(404, "Demanda não encontrada")
    novo = body.status
    if novo not in FLUXO_STATUS.get(d.status, []):
        raise HTTPException(400, f"Transição inválida: {d.status} → {novo}")
    if novo in STATUS_FECHADOS:
        exigir(usuario, "gestor")        # encerrar/arquivar: gestor+
    else:
        exigir(usuario, "advogado")
    anterior = d.status
    d.status = novo
    if novo == "encerrado":
        agora = datetime.utcnow()
        for a in db.query(models.Alocacao).filter(models.Alocacao.demanda_id == did).all():
            if a.status == "ativo":
                a.status, a.encerrado_em = "encerrado", agora
                prof = db.get(models.Usuario, a.profissional_id)
                if prof and prof.carga_atual > 0:
                    prof.carga_atual -= 1
    db.add(models.Movimentacao(demanda_id=did, profissional_id=usuario.id,
                               status_anterior=anterior, status_novo=novo,
                               observacao=body.observacao))
    db.commit()
    db.refresh(d)
    return s_demanda(d, db, completo=True)


@app.post("/api/demandas/{did}/alocacoes")
def alocar(did: str, body: schemas.AlocacaoIn, usuario: models.Usuario = Depends(usuario_atual),
           db: Session = Depends(get_db)):
    exigir(usuario, "gestor")            # alocar profissional: gestor+
    d = db.get(models.Demanda, did)
    if not d:
        raise HTTPException(404, "Demanda não encontrada")
    prof = db.get(models.Usuario, body.profissional_id)
    if not prof or not prof.ativo:
        raise HTTPException(400, "Profissional inválido")
    existe = db.query(models.Alocacao).filter(
        models.Alocacao.demanda_id == did, models.Alocacao.profissional_id == body.profissional_id).first()
    if existe:
        raise HTTPException(409, "Profissional já alocado nesta demanda")
    if prof.carga_atual >= prof.carga_maxima:
        raise HTTPException(400, f"{prof.nome} está com carga máxima ({prof.carga_maxima}) atingida")
    if body.responsavel_principal:
        for a in db.query(models.Alocacao).filter(
                models.Alocacao.demanda_id == did, models.Alocacao.responsavel_principal == True).all():
            a.responsavel_principal = False
    db.add(models.Alocacao(
        demanda_id=did, profissional_id=body.profissional_id, papel=body.papel,
        responsavel_principal=body.responsavel_principal, horas_estimadas=body.horas_estimadas,
    ))
    prof.carga_atual += 1
    if d.status == "triagem":
        anterior = d.status
        d.status = "alocacao"
        db.add(models.Movimentacao(demanda_id=did, profissional_id=usuario.id,
                                   status_anterior=anterior, status_novo="alocacao",
                                   observacao=f"Profissional alocado: {prof.nome}"))
    db.commit()
    return s_demanda(d, db, completo=True)


@app.delete("/api/demandas/{did}/alocacoes/{aid}")
def remover_alocacao(did: str, aid: str, usuario: models.Usuario = Depends(usuario_atual),
                     db: Session = Depends(get_db)):
    exigir(usuario, "gestor")
    a = db.get(models.Alocacao, aid)
    if not a or a.demanda_id != did:
        raise HTTPException(404, "Alocação não encontrada")
    prof = db.get(models.Usuario, a.profissional_id)
    if prof and prof.carga_atual > 0 and a.status == "ativo":
        prof.carga_atual -= 1
    db.delete(a)
    db.commit()
    d = db.get(models.Demanda, did)
    return s_demanda(d, db, completo=True)


# --------------------------------------------------------------------------- #
# DASHBOARD / KPIs (controladoria — gestor leitura, sócio total)
# --------------------------------------------------------------------------- #
@app.get("/api/dashboard")
def dashboard(usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    exigir(usuario, "gestor")
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    demandas = db.query(models.Demanda).all()
    ativas = [d for d in demandas if d.status not in STATUS_FECHADOS]

    encerradas_mes = [d for d in demandas if d.status == "encerrado"
                      and d.atualizado_em and d.atualizado_em.date() >= inicio_mes]

    com_prazo = [d for d in ativas if d.prazo_interno]
    dentro = [d for d in com_prazo if d.prazo_interno >= hoje]
    vencidas = [d for d in com_prazo if d.prazo_interno < hoje]
    vencendo48 = [d for d in com_prazo if hoje <= d.prazo_interno <= hoje + timedelta(days=2)]
    pct_sla = round(len(dentro) / len(com_prazo) * 100, 1) if com_prazo else 100.0

    # Produção por núcleo (encerradas no mês)
    nucleos = db.query(models.Nucleo).all()
    nome_nuc = {n.id: n.nome for n in nucleos}
    prod = {}
    for d in encerradas_mes:
        prod[nome_nuc.get(d.nucleo_id, "—")] = prod.get(nome_nuc.get(d.nucleo_id, "—"), 0) + 1
    producao_nucleo = [{"nucleo": k, "total": v} for k, v in sorted(prod.items(), key=lambda x: -x[1])]

    # Aging das demandas em aberto
    faixas = {"normal": 0, "monitorar": 0, "atencao": 0, "critico": 0}
    for d in ativas:
        dias = (hoje - d.criado_em.date()).days if d.criado_em else 0
        if dias > 60:
            faixas["critico"] += 1
        elif dias > 30:
            faixas["atencao"] += 1
        elif dias > 15:
            faixas["monitorar"] += 1
        else:
            faixas["normal"] += 1

    # Throughput dos últimos 12 meses (encerradas por mês)
    meses = []
    ref = inicio_mes
    for _ in range(12):
        meses.append((ref.year, ref.month))
        ref = (ref - timedelta(days=1)).replace(day=1)
    meses.reverse()
    contagem = {ym: 0 for ym in meses}
    for d in demandas:
        if d.status == "encerrado" and d.atualizado_em:
            ym = (d.atualizado_em.year, d.atualizado_em.month)
            if ym in contagem:
                contagem[ym] += 1
    throughput = [{"mes": f"{y}-{m:02d}", "total": contagem[(y, m)]} for (y, m) in meses]

    # Aderência ao SLA por profissional (responsável principal)
    por_prof = {}
    alocs = db.query(models.Alocacao).filter(models.Alocacao.responsavel_principal == True).all()
    dem_map = {d.id: d for d in demandas}
    for a in alocs:
        d = dem_map.get(a.demanda_id)
        if not d:
            continue
        por_prof.setdefault(a.profissional_id, {"total": 0, "ok": 0})
        por_prof[a.profissional_id]["total"] += 1
        if d.status in STATUS_FECHADOS or (d.prazo_interno and d.prazo_interno >= hoje) or not d.prazo_interno:
            por_prof[a.profissional_id]["ok"] += 1
    ranking = []
    for pid, v in por_prof.items():
        u = db.get(models.Usuario, pid)
        if not u or v["total"] == 0:
            continue
        ranking.append({"profissional": u.nome,
                        "pct": round(v["ok"] / v["total"] * 100, 1),
                        "total": v["total"]})
    ranking.sort(key=lambda x: -x["pct"])

    # Carteira financeira
    valores = [float(d.valor_causa) for d in ativas if d.valor_causa is not None]
    carteira = {
        "valor_total": round(sum(valores), 2),
        "alto": len([v for v in valores if v > 500_000]),
        "medio": len([v for v in valores if 50_000 <= v <= 500_000]),
        "baixo": len([v for v in valores if v < 50_000]),
    }

    return {
        "cards": {
            "demandas_ativas": len(ativas),
            "encerradas_mes": len(encerradas_mes),
            "sla_aderencia": pct_sla,
            "vencendo_48h": len(vencendo48),
            "vencidas": len(vencidas),
            "aguardando_triagem": len([d for d in ativas if d.status == "triagem"]),
        },
        "producao_nucleo": producao_nucleo,
        "aging": faixas,
        "throughput": throughput,
        "ranking_sla": ranking[:8],
        "carteira": carteira,
    }


# --------------------------------------------------------------------------- #
# ADMINISTRAÇÃO (somente master)
# --------------------------------------------------------------------------- #
@app.post("/api/admin/limpar-demo")
def limpar_demo(usuario: models.Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    """Apaga TODOS os dados (demandas, núcleos e usuários), mantendo apenas o
    master logado. Usado para sair dos dados de exemplo e começar do zero."""
    exigir(usuario, "master")
    # 1) tabelas filhas
    db.query(models.Movimentacao).delete(synchronize_session=False)
    db.query(models.EventoSla).delete(synchronize_session=False)
    db.query(models.Alocacao).delete(synchronize_session=False)
    db.query(models.Demanda).delete(synchronize_session=False)
    # 2) quebra os vínculos de FK antes de remover núcleos/usuários
    db.query(models.Nucleo).update({models.Nucleo.gestor_id: None}, synchronize_session=False)
    db.query(models.Usuario).update(
        {models.Usuario.nucleo_id: None, models.Usuario.gestor_id: None, models.Usuario.carga_atual: 0},
        synchronize_session=False,
    )
    # 3) remove todos os usuários, exceto o master atual, e todos os núcleos
    db.query(models.Usuario).filter(models.Usuario.id != usuario.id).delete(synchronize_session=False)
    db.query(models.Nucleo).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "mensagem": "Dados de demonstração removidos. Apenas o login master foi mantido."}


# --------------------------------------------------------------------------- #
# Metadados úteis para os formulários do frontend
# --------------------------------------------------------------------------- #
@app.get("/api/meta")
def meta(usuario: models.Usuario = Depends(usuario_atual)):
    return {
        "tipos_demanda": ["trabalhista", "tributario", "civil", "empresarial", "imobiliario", "criminal"],
        "prioridades": ["urgente", "alta", "normal", "baixa"],
        "perfis": ["master", "socio", "gestor", "advogado", "estagiario"],
        "papeis": ["responsavel", "colaborador", "revisor"],
        "status": ["triagem", "alocacao", "execucao", "encerrado", "arquivado"],
    }


# --------------------------------------------------------------------------- #
# Frontend estático (precisa ficar por último — captura todas as demais rotas)
# --------------------------------------------------------------------------- #
app.mount("/", StaticFiles(directory="static", html=True), name="static")
