"""Seguridad: hashing de contraseñas, tokens JWT y reglas de fortaleza.

Buenas prácticas aplicadas:
  * Contraseñas NUNCA en texto plano: ``bcrypt`` con coste configurable.
  * Comparación en tiempo constante (bcrypt lo hace internamente) para
    mitigar ataques de temporización.
  * Tokens JWT firmados (HS256) con expiración corta y tipo declarado.
  * Validación de fortaleza de contraseña antes de aceptarla.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from backend.nucleo.configuracion import configuracion

# ----------------------------------------------------------------------
# Contraseñas
# ----------------------------------------------------------------------
_LARGO_MINIMO = 10
_LARGO_MAXIMO = 128


class ContrasenaDebilError(ValueError):
    """La contraseña no cumple la política de fortaleza."""


def validar_fortaleza_contrasena(contrasena: str) -> None:
    """Aplica la política de contraseñas del sistema administrativo."""
    if len(contrasena) < _LARGO_MINIMO:
        raise ContrasenaDebilError(f"La contraseña debe tener al menos {_LARGO_MINIMO} caracteres.")
    if len(contrasena) > _LARGO_MAXIMO:
        raise ContrasenaDebilError("La contraseña es demasiado larga.")
    if not re.search(r"[a-z]", contrasena):
        raise ContrasenaDebilError("La contraseña debe incluir al menos una letra minúscula.")
    if not re.search(r"[A-Z]", contrasena):
        raise ContrasenaDebilError("La contraseña debe incluir al menos una letra mayúscula.")
    if not re.search(r"\d", contrasena):
        raise ContrasenaDebilError("La contraseña debe incluir al menos un número.")
    if not re.search(r"[^\w\s]", contrasena):
        raise ContrasenaDebilError("La contraseña debe incluir al menos un símbolo.")
    comunes = {"contrasena", "password", "1234567890", "administrador", "admin123456"}
    if contrasena.lower() in comunes:
        raise ContrasenaDebilError("La contraseña es demasiado común.")


def hash_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de la contraseña (con salt aleatorio)."""
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """Compara la contraseña con su hash en tiempo constante."""
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verificar_hash_falso(contrasena: str) -> None:
    """Ejecuta un hashing descartable para igualar los tiempos de respuesta
    cuando el usuario no existe (evita *user enumeration* por temporización)."""
    bcrypt.checkpw(contrasena.encode("utf-8"), b"$2b$12$" + b"x" * 53)


# ----------------------------------------------------------------------
# Tokens JWT
# ----------------------------------------------------------------------
def crear_token(datos: dict[str, Any], minutos: int | None = None, tipo: str = "acceso") -> str:
    """Firma un JWT con expiración y tipo (acceso | refresco)."""
    ahora = datetime.now(tz=timezone.utc)
    expiracion = ahora + timedelta(
        minutes=minutos if minutos is not None else configuracion.minutos_expiracion_acceso
    )
    payload = {
        **datos,
        "tipo": tipo,
        "iat": int(ahora.timestamp()),
        "exp": int(expiracion.timestamp()),
        "iss": configuracion.nombre_app,
        "jti": secrets.token_hex(16),  # identificador único del token
    }
    return jwt.encode(payload, configuracion.clave_secreta, algorithm=configuracion.algoritmo_jwt)


def crear_token_acceso(usuario: dict) -> str:
    return crear_token(
        {
            "sub": str(usuario["id"]),
            "correo": usuario["correo"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
        },
        tipo="acceso",
    )


def crear_token_refresco(usuario: dict) -> str:
    return crear_token(
        {"sub": str(usuario["id"]), "jti_origen": secrets.token_hex(8)},
        minutos=configuracion.dias_expiracion_refresco * 24 * 60,
        tipo="refresco",
    )


class TokenInvalidoError(ValueError):
    """El token es inválido, expiró o fue manipulado."""


def decodificar_token(token: str, tipo_esperado: str = "acceso") -> dict[str, Any]:
    """Valida firma, expiración e issuer. Lanza TokenInvalidoError si falla."""
    try:
        datos = jwt.decode(
            token,
            configuracion.clave_secreta,
            algorithms=[configuracion.algoritmo_jwt],
            issuer=configuracion.nombre_app,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenInvalidoError("La sesión expiró. Inicia sesión de nuevo.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidoError("Token inválido.") from exc

    if datos.get("tipo") != tipo_esperado:
        raise TokenInvalidoError("Tipo de token incorrecto.")
    return datos
