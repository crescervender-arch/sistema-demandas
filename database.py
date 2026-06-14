"""Configuração do banco de dados SQL (SQLAlchemy).

Por padrão usa SQLite (arquivo demandas.db) — zero instalação e roda em qualquer
máquina. Para produção/Postgres basta definir a variável de ambiente DATABASE_URL,
ex.: postgresql+psycopg://user:senha@host:5432/demandas
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./demandas.db")

# Railway/Render entregam a URL como "postgres://" ou "postgresql://" (driver
# padrão = psycopg2). Forçamos o driver psycopg (v3), que é o instalado.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()


def get_db():
    """Dependência FastAPI: abre uma sessão por request e garante o fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
