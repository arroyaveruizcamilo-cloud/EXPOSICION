"""Rutas de autenticación: login, logout, refresco y perfil."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from backend.dominio.repositorio import Repositorio
from backend.nucleo.configuracion import configuracion
from backend.seguridad.dependencias import obtener_repositorio, usuario_actual
from backend.servicios.autenticacion import (
    AutenticacionError,
    CuentaBloqueadaError,
    ServicioAutenticacion,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


# ----------------------------------------------------------------------
# Esquemas
# ----------------------------------------------------------------------
class Credenciales(BaseModel):
    correo: EmailStr = Field(..., examples=["admin@transmaquinaria.com"])
    contrasena: str = Field(..., min_length=1, max_length=200, examples=["Admin#2026*Seg"])


# ----------------------------------------------------------------------
# Utilidades de cookies
# ----------------------------------------------------------------------
def _fijar_cookies(respuesta: Response, tokens: dict) -> None:
    """Guarda los tokens en cookies HttpOnly (no accesibles por JavaScript)."""
    respuesta.set_cookie(
        key=configuracion.cookie_acceso,
        value=tokens["token_acceso"],
        httponly=True,
        samesite="lax",
        secure=configuracion.cookie_segura,
        max_age=configuracion.minutos_expiracion_acceso * 60,
        path="/",
    )
    respuesta.set_cookie(
        key=configuracion.cookie_refresco,
        value=tokens["token_refresco"],
        httponly=True,
        samesite="lax",
        secure=configuracion.cookie_segura,
        max_age=configuracion.dias_expiracion_refresco * 24 * 3600,
        path="/",
    )


def _limpiar_cookies(respuesta: Response) -> None:
    respuesta.delete_cookie(configuracion.cookie_acceso, path="/")
    respuesta.delete_cookie(configuracion.cookie_refresco, path="/")


def _datos_cliente(peticion: Request) -> tuple[str, str]:
    ip = peticion.client.host if peticion.client else "desconocida"
    user_agent = peticion.headers.get("user-agent", "desconocido")
    return ip, user_agent


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.post("/login")
def login(
    credenciales: Credenciales,
    peticion: Request,
    respuesta: Response,
    repositorio: Repositorio = Depends(obtener_repositorio),
) -> dict:
    """Inicia sesión con correo y contraseña."""
    servicio = ServicioAutenticacion(repositorio)
    ip, user_agent = _datos_cliente(peticion)
    try:
        resultado = servicio.iniciar_sesion(
            credenciales.correo, credenciales.contrasena, ip, user_agent
        )
    except CuentaBloqueadaError as exc:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc
    except AutenticacionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _fijar_cookies(respuesta, resultado)
    return {"usuario": resultado["usuario"], "token_acceso": resultado["token_acceso"]}


@router.post("/logout")
def logout(
    peticion: Request,
    respuesta: Response,
    usuario: dict = Depends(usuario_actual),
    repositorio: Repositorio = Depends(obtener_repositorio),
) -> dict:
    """Cierra la sesión y revoca el token actual."""
    ip, _ = _datos_cliente(peticion)
    ServicioAutenticacion(repositorio).cerrar_sesion(usuario["jti"], usuario["id"], ip)
    _limpiar_cookies(respuesta)
    return {"mensaje": "Sesión cerrada correctamente."}


@router.post("/refrescar")
def refrescar(
    peticion: Request,
    respuesta: Response,
    repositorio: Repositorio = Depends(obtener_repositorio),
) -> dict:
    """Renueva el token de acceso usando el token de refresco."""
    token = peticion.cookies.get(configuracion.cookie_refresco)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No hay sesión que refrescar.")
    ip, user_agent = _datos_cliente(peticion)
    try:
        tokens = ServicioAutenticacion(repositorio).refrescar(token, ip, user_agent)
    except AutenticacionError as exc:
        _limpiar_cookies(respuesta)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    respuesta.set_cookie(
        configuracion.cookie_acceso, tokens["token_acceso"],
        httponly=True, samesite="lax", secure=configuracion.cookie_segura,
        max_age=configuracion.minutos_expiracion_acceso * 60, path="/",
    )
    return {"token_acceso": tokens["token_acceso"]}


@router.get("/perfil")
def perfil(usuario: dict = Depends(usuario_actual)) -> dict:
    """Datos del usuario autenticado (para pintar el panel)."""
    return {
        "id": usuario["id"],
        "correo": usuario["correo"],
        "nombre": usuario["nombre"],
        "rol": usuario["rol"],
    }
