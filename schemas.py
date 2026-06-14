"""Schemas Pydantic para validação dos corpos de request."""
from typing import Optional
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    senha: str


class UsuarioIn(BaseModel):
    nome: str
    email: str
    senha: Optional[str] = None          # obrigatório só na criação
    perfil_acesso: str
    cargo: Optional[str] = None
    oab: Optional[str] = None
    celular: Optional[str] = None
    nucleo_id: Optional[str] = None
    gestor_id: Optional[str] = None
    carga_maxima: int = 30
    ativo: bool = True


class NucleoIn(BaseModel):
    nome: str
    sigla: str
    gestor_id: Optional[str] = None
    ativo: bool = True


class DemandaIn(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    tipo_demanda: str
    prioridade: str = "normal"
    nucleo_id: str
    valor_causa: Optional[float] = None
    prazo_legal: Optional[str] = None     # 'YYYY-MM-DD'
    prazo_interno: Optional[str] = None
    numero_processo: Optional[str] = None
    tribunal: Optional[str] = None
    fase_processual: Optional[str] = None


class StatusIn(BaseModel):
    status: str
    observacao: Optional[str] = None


class AlocacaoIn(BaseModel):
    profissional_id: str
    papel: str = "colaborador"
    responsavel_principal: bool = False
    horas_estimadas: Optional[int] = None


class SenhaIn(BaseModel):
    senha_atual: Optional[str] = None
    nova_senha: str = Field(min_length=4)
