"""Autenticação: hash de senha (PBKDF2, stdlib) e token assinado (HMAC, stdlib).

Sem dependências externas de criptografia — evita problemas de compilação no
Windows e mantém o setup leve. O modelo de token é stateless, no espírito do JWT
descrito na spec (assinatura HMAC-SHA256 + expiração).
"""
import base64
import hashlib
import hmac
import json
import os
import time

SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta-em-producao")
TOKEN_HORAS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_HOURS", "8"))

# Hierarquia de perfis (master acima de tudo) — base do RBAC.
PERFIL_NIVEL = {
    "master": 5,
    "socio": 4,
    "gestor": 3,
    "advogado": 2,
    "estagiario": 1,
}


def hash_senha(senha: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 120_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        salt_b64, dk_b64 = armazenado.split("$")
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(dk_b64)
        atual = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 120_000)
        return hmac.compare_digest(atual, esperado)
    except Exception:
        return False


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def criar_token(usuario_id: str) -> str:
    payload = {"sub": usuario_id, "exp": int(time.time()) + TOKEN_HORAS * 3600}
    body = _b64url(json.dumps(payload).encode())
    sig = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def ler_token(token: str):
    """Retorna o usuario_id se o token é válido e não expirou; senão None."""
    try:
        body, sig = token.split(".")
        esperado = hmac.new(SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, esperado):
            return None
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")
    except Exception:
        return None


def nivel(perfil: str) -> int:
    return PERFIL_NIVEL.get(perfil, 0)
