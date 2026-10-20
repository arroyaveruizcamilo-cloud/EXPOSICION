"""Dependencias de seguridad para FastAPI: lectura de cookies y roles.

El token viaja en una **cookie HttpOnly** (no accesible desde JavaScript, lo que
mitiga el robo de tokens por XSS) y además se acepta la cabecera
``Authorization: Bearer`` para pruebas con herramientas como curl.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from backend.dominio.repositorio import Repositorio
from backend.nucleo.configuracion import configuracion
from backend.seguridad.seguridad import TokenInvalidoError, decodificar_token


def obtener_repositorio() -> Repositorio:
    """Repositorio compartido (inyectable en las demás dependencias)."""
    return Repositorio()


def _token_de_peticion(peticion: Request) -> str | None:
    token = peticion.cookies.get(configuracion.cookie_acceso)
    if token:
        return token
    cabecera = peticion.headers.get("Authorization", "")
    if cabecera.startswith("Bearer "):
        return cabecera[7:].strip()
    return None


def usuario_actual(
    peticion: Request,
    repositorio: Repositorio = Depends(obtener_repositorio),
) -> dict:
    """Valida el token y devuelve el usuario autenticado."""
    token = _token_de_peticion(peticion)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Inicia sesión para continuar.",
        )
    try:
        datos = decodificar_token(token, "acceso")
    except TokenInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    # La sesión debe seguir vigente (permite cerrar sesión de forma efectiva).
    if not repositorio.sesion_activa(datos["jti"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión fue cerrada. Inicia sesión de nuevo.",
        )

    usuario = repositorio.buscar_usuario_por_correo(datos["correo"])
    if usuario is None or not int(usuario["activo"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cuenta no disponible.")

    return {
        "id": usuario["id"],
        "correo": usuario["correo"],
        "nombre": usuario["nombre"],
        "rol": usuario["rol"],
        "jti": datos["jti"],
    }


def requiere_rol(*roles: str):
    """Genera una dependencia que exige uno de los roles indicados."""

    def verificador(usuario: dict = Depends(usuario_actual)) -> dict:
        if roles and usuario["rol"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para realizar esta acción.",
            )
        return usuario

    return verificador
