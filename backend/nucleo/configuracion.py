"""Configuración central del backend administrativo.

Los valores sensibles se leen de variables de entorno. En desarrollo, si no
existen, se generan/usan valores por defecto SEGUROS (la clave secreta se
genera aleatoriamente en cada arranque y se avisa por consola).
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Configuracion:
    """Parámetros de la aplicación (inmutables)."""

    nombre_app: str = "TransMaquinaria — Panel administrativo"
    version: str = "2.0.0"

    # Rutas
    ruta_raiz: Path = RAIZ_PROYECTO
    ruta_base_datos: Path = field(
        default_factory=lambda: RAIZ_PROYECTO / "database" / "almacen" / "transporte_maquinaria.db"
    )
    ruta_frontend: Path = field(default_factory=lambda: RAIZ_PROYECTO / "frontend")

    # --- Seguridad -----------------------------------------------------
    # Clave para firmar los JWT. SIEMPRE debe venir del entorno en producción.
    clave_secreta: str = field(default_factory=lambda: os.getenv("TM_SECRET_KEY") or secrets.token_urlsafe(48))
    algoritmo_jwt: str = "HS256"
    minutos_expiracion_acceso: int = int(os.getenv("TM_EXPIRA_MINUTOS", "30"))
    dias_expiracion_refresco: int = int(os.getenv("TM_EXPIRA_DIAS_REFRESCO", "7"))

    # Cookies seguras (HttpOnly + SameSite=Lax; Secure se activa con HTTPS).
    cookie_acceso: str = "tm_acceso"
    cookie_refresco: str = "tm_refresco"
    cookie_segura: bool = os.getenv("TM_COOKIE_SEGURA", "0") == "1"

    # Control de fuerza bruta
    max_intentos_fallidos: int = int(os.getenv("TM_MAX_INTENTOS", "5"))
    minutos_bloqueo: int = int(os.getenv("TM_MINUTOS_BLOQUEO", "15"))
    segundos_bloqueo_min: int = int(os.getenv("TM_BLOQUEO_MIN_SEG", "2"))
    segundos_bloqueo_max: int = int(os.getenv("TM_BLOQUEO_MAX_SEG", "10"))

    # Duración de la sesión (idle) para auditoría
    minutos_sesion_inactiva: int = int(os.getenv("TM_SESION_INACTIVA", "30"))

    # CORS: en producción deben indicarse orígenes concretos, nunca "*".
    origenes_permitidos: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("TM_ORIGENES", "http://127.0.0.1:8000,http://localhost:8000").split(",") if o.strip()
        )
    )

    def clave_secreta_es_temporal(self) -> bool:
        return "TM_SECRET_KEY" not in os.environ


configuracion = Configuracion()
