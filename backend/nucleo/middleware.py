"""Middleware de cabeceras de seguridad y limitación de peticiones.

Cabeceras aplicadas a TODAS las respuestas:
  * Content-Security-Policy: limita de dónde se cargan scripts/estilos.
  * X-Content-Type-Options: evita adivinar el tipo MIME.
  * X-Frame-Options: impide incrustar el panel en otro sitio (clickjacking).
  * Referrer-Policy y Permissions-Policy: mínima información al exterior.
  * Cache-Control en respuestas de API: evita guardar datos sensibles.
"""
from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class MiddlewareSeguridad(BaseHTTPMiddleware):
    """Añade cabeceras de seguridad a cada respuesta."""

    async def dispatch(self, peticion: Request, llamar_siguiente) -> Response:
        respuesta = await llamar_siguiente(peticion)
        respuesta.headers["Content-Security-Policy"] = CSP
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        respuesta.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if peticion.url.path.startswith("/api/"):
            respuesta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return respuesta


class LimitadorPeticiones(BaseHTTPMiddleware):
    """Limitador simple en memoria (ventana fija) para frenar abusos.

    Mantiene **contadores separados** para el login y para el resto de la API,
    de modo que usar el panel no consume el cupo anti fuerza bruta (y al revés).
    Suficiente para una demo; en producción se recomienda Redis o similar.
    """

    def __init__(
        self,
        app,
        maximo_general: int = 240,
        maximo_login: int = 15,
        ventana_segundos: int = 60,
    ) -> None:
        super().__init__(app)
        self._maximo_general = maximo_general
        self._maximo_login = maximo_login
        self._ventana = ventana_segundos
        self._general: dict[str, list[float]] = defaultdict(list)
        self._login: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, peticion: Request, llamar_siguiente) -> Response:
        ip = peticion.client.host if peticion.client else "desconocida"
        ahora = time.time()
        es_login = peticion.url.path.endswith("/auth/login")

        # Cubo independiente según el tipo de petición.
        cubo = self._login if es_login else self._general
        limite = self._maximo_login if es_login else self._maximo_general

        recientes = [t for t in cubo[ip] if ahora - t < self._ventana]
        recientes.append(ahora)
        cubo[ip] = recientes

        if len(recientes) > limite:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas solicitudes. Espera un momento e inténtalo de nuevo."},
            )
        return await llamar_siguiente(peticion)
