"""Modelos ORM — espelham o schema da especificação técnica (seção 2).

Adaptações para o app web:
- IDs em UUID (hex) como String, compatível com SQLite e Postgres.
- A tabela `usuarios` unifica login + profissional (cada login É um profissional,
  exceto o perfil 'master', que é o administrador do sistema).
"""
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Date, Numeric, Text, ForeignKey,
)

from database import Base


def uid() -> str:
    return uuid.uuid4().hex


class Usuario(Base):
    """Login + profissional. perfil_acesso: master|socio|gestor|advogado|estagiario."""
    __tablename__ = "usuarios"

    id = Column(String, primary_key=True, default=uid)
    nome = Column(String(150), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    oab = Column(String(30))
    cargo = Column(String(60))
    perfil_acesso = Column(String(20), nullable=False)
    nucleo_id = Column(String, ForeignKey("nucleos.id"))
    gestor_id = Column(String, ForeignKey("usuarios.id"))
    carga_maxima = Column(Integer, default=30)
    carga_atual = Column(Integer, default=0)
    celular = Column(String(20))
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Nucleo(Base):
    __tablename__ = "nucleos"

    id = Column(String, primary_key=True, default=uid)
    nome = Column(String(120), nullable=False)
    sigla = Column(String(10), nullable=False, unique=True)
    gestor_id = Column(String, ForeignKey("usuarios.id"))
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class Demanda(Base):
    __tablename__ = "demandas"

    id = Column(String, primary_key=True, default=uid)
    titulo = Column(String(250), nullable=False)
    descricao = Column(Text)
    tipo_demanda = Column(String(50), nullable=False)        # trabalhista|tributario|civil|empresarial|imobiliario
    status = Column(String(30), nullable=False, default="triagem")  # triagem|alocacao|execucao|encerrado|arquivado
    prioridade = Column(String(20), nullable=False, default="normal")  # urgente|alta|normal|baixa
    nucleo_id = Column(String, ForeignKey("nucleos.id"), nullable=False)
    criado_por = Column(String, ForeignKey("usuarios.id"), nullable=False)
    valor_causa = Column(Numeric(15, 2))
    prazo_legal = Column(Date)
    prazo_interno = Column(Date)
    numero_processo = Column(String(50))
    tribunal = Column(String(100))
    fase_processual = Column(String(60))
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alocacao(Base):
    __tablename__ = "alocacoes"

    id = Column(String, primary_key=True, default=uid)
    demanda_id = Column(String, ForeignKey("demandas.id"), nullable=False)
    profissional_id = Column(String, ForeignKey("usuarios.id"), nullable=False)
    papel = Column(String(30), default="colaborador")        # responsavel|colaborador|revisor
    responsavel_principal = Column(Boolean, default=False)
    horas_estimadas = Column(Integer)
    horas_realizadas = Column(Integer, default=0)
    alocado_em = Column(DateTime, default=datetime.utcnow)
    encerrado_em = Column(DateTime)
    status = Column(String(20), default="ativo")             # ativo|encerrado|transferido


class Movimentacao(Base):
    """Audit trail — toda mudança de status registrada (imutável)."""
    __tablename__ = "movimentacoes"

    id = Column(String, primary_key=True, default=uid)
    demanda_id = Column(String, ForeignKey("demandas.id"), nullable=False)
    profissional_id = Column(String, ForeignKey("usuarios.id"), nullable=False)
    status_anterior = Column(String(30))
    status_novo = Column(String(30), nullable=False)
    observacao = Column(Text)
    ocorrido_em = Column(DateTime, default=datetime.utcnow)


class EventoSla(Base):
    __tablename__ = "eventos_sla"

    id = Column(String, primary_key=True, default=uid)
    demanda_id = Column(String, ForeignKey("demandas.id"), nullable=False)
    tipo_alerta = Column(String(30), nullable=False)         # alerta_72h|alerta_48h|alerta_24h|vencido
    gatilho_em = Column(DateTime, nullable=False)
    disparado = Column(Boolean, default=False)
    canal = Column(String(30), default="todos")
    criado_em = Column(DateTime, default=datetime.utcnow)
