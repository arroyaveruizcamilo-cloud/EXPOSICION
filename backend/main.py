"""Punto de entrada del backend (FastAPI).

Ejecutar:
    python -m backend.main
    # o
    python -m uvicorn backend.main:app --reload --port 8000

El frontend (HTML/CSS/JS) se sirve desde ``frontend/`` como archivos separados;
el backend solo expone la API en ``/api/...``.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.nucleo.configuracion import configuracion  # noqa: E402
from backend.nucleo.middleware import LimitadorPeticiones, MiddlewareSeguridad  # noqa: E402
from backend.rutas import autenticacion, operaciones  # noqa: E402
from database.scripts.crear_base_datos import asegurar_base_datos  # noqa: E402

# Garantiza que exista la base de datos antes de levantar la API.
asegurar_base_datos()

app = FastAPI(
    title=configuracion.nombre_app,
    version=configuracion.version,
    description=(
        "API del panel administrativo de transporte de maquinaria amarilla, "
        "pesada y extradimensionada. Incluye autenticación con JWT en cookies "
        "HttpOnly, bloqueo por intentos fallidos y auditoría."
    ),
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# --- Middlewares (el orden importa: el último añadido se ejecuta primero) ---
app.add_middleware(LimitadorPeticiones, maximo_login=15, maximo_general=240)
app.add_middleware(MiddlewareSeguridad)

# --- Rutas ---
app.include_router(autenticacion.router)
app.include_router(operaciones.router)

# --- Archivos estáticos del frontend (carpetas separadas) ---
app.mount("/css", StaticFiles(directory=configuracion.ruta_frontend / "activos" / "css"), name="css")
app.mount("/js", StaticFiles(directory=configuracion.ruta_frontend / "activos" / "js"), name="js")


@app.get("/health", tags=["Sistema"])
def health() -> dict:
    """Comprobación de vida del servicio."""
    return {"estado": "ok", "app": configuracion.nombre_app, "version": configuracion.version}


@app.get("/", include_in_schema=False)
def login_page() -> FileResponse:
    """Página de inicio de sesión."""
    return FileResponse(configuracion.ruta_frontend / "vistas" / "login.html")


@app.get("/panel", include_in_schema=False)
def panel_page() -> FileResponse:
    """Panel administrativo (la protección real la hace la API con JWT)."""
    return FileResponse(configuracion.ruta_frontend / "vistas" / "index.html")


@app.exception_handler(404)
async def no_encontrado(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Recurso no encontrado."})


if __name__ == "__main__":
    import uvicorn

    if configuracion.clave_secreta_es_temporal():
        print(
            "\n[AVISO] No se definió TM_SECRET_KEY: se generó una clave temporal.\n"
            "        En producción exporta TM_SECRET_KEY y TM_COOKIE_SEGURA=1.\n"
        )
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
