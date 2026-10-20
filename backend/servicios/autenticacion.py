"""Servicio de autenticación: registro de intentos, bloqueo y emisión de tokens.

Reglas de seguridad aplicadas en el inicio de sesión:

  1. **Mensaje de error genérico** ("correo o contraseña incorrectos") tanto si
     el correo no existe como si la contraseña falla: evita enumerar usuarios.
  2. **Comparación en tiempo constante**: cuando el usuario no existe se hace un
     hashing descartable para no revelar por temporización qué correos existen.
  3. **Bloqueo temporal** de la cuenta tras varios intentos fallidos.
  4. **Retardo progresivo** para frenar ataques automatizados.
  5. **Auditoría** de cada intento y de cada inicio/cierre de sesión.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone

from backend.dominio.repositorio import Repositorio
from backend.nucleo.configuracion import configuracion
from backend.seguridad.seguridad import (
    crear_token_acceso,
    crear_token_refresco,
    decodificar_token,
    verificar_contrasena,
    verificar_hash_falso,
)


class AutenticacionError(Exception):
    """Fallo de autenticación con mensaje apto para mostrar al usuario."""


class CuentaBloqueadaError(AutenticacionError):
    """La cuenta está bloqueada temporalmente por intentos fallidos."""


class ServicioAutenticacion:
    """Orquesta el inicio y cierre de sesión sobre el repositorio."""

    def __init__(self, repositorio: Repositorio) -> None:
        self._repositorio = repositorio

    # ------------------------------------------------------------------
    def iniciar_sesion(self, correo: str, contrasena: str, ip: str, user_agent: str) -> dict:
        """Valida credenciales y devuelve los tokens + datos del usuario."""
        correo = correo.strip().lower()
        if not correo or not contrasena:
            raise AutenticacionError("Debes indicar correo y contraseña.")

        usuario = self._repositorio.buscar_usuario_por_correo(correo)

        if usuario is None:
            verificar_hash_falso(contrasena)  # iguala el tiempo de respuesta
            self._repositorio.registrar_intento_fallido(
                correo, ip, user_agent, configuracion.max_intentos_fallidos, configuracion.minutos_bloqueo
            )
            self._espera_progresiva(correo)
            raise AutenticacionError("Correo o contraseña incorrectos.")

        if not int(usuario["activo"]):
            raise AutenticacionError("La cuenta está desactivada. Contacta al administrador.")

        bloqueado_hasta = usuario.get("bloqueado_hasta")
        if bloqueado_hasta:
            limite = datetime.strptime(bloqueado_hasta, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < limite:
                restante = int((limite - datetime.now()).total_seconds() // 60) + 1
                raise CuentaBloqueadaError(
                    f"Cuenta bloqueada temporalmente por intentos fallidos. Reintenta en {restante} min."
                )

        if not verificar_contrasena(contrasena, usuario["hash_contrasena"]):
            self._repositorio.registrar_intento_fallido(
                correo, ip, user_agent, configuracion.max_intentos_fallidos, configuracion.minutos_bloqueo
            )
            self._repositorio.registrar_auditoria(usuario["id"], "LOGIN_FALLIDO", "Contraseña incorrecta", ip)
            self._espera_progresiva(correo)
            raise AutenticacionError("Correo o contraseña incorrectos.")

        # Éxito
        self._repositorio.registrar_acceso_exitoso(usuario["id"])
        self._repositorio.registrar_intento_exitoso(correo, ip, user_agent)

        acceso = crear_token_acceso(usuario)
        refresco = crear_token_refresco(usuario)

        datos_acceso = decodificar_token(acceso, "acceso")
        expira = datetime.fromtimestamp(datos_acceso["exp"], tz=timezone.utc).replace(tzinfo=None)
        self._repositorio.crear_sesion(
            jti=datos_acceso["jti"],
            usuario_id=usuario["id"],
            expira_en=expira.strftime("%Y-%m-%d %H:%M:%S"),
            ip=ip,
            user_agent=user_agent,
        )
        self._repositorio.registrar_auditoria(usuario["id"], "LOGIN", "Inicio de sesión exitoso", ip)

        return {
            "token_acceso": acceso,
            "token_refresco": refresco,
            "usuario": {
                "id": usuario["id"],
                "correo": usuario["correo"],
                "nombre": usuario["nombre"],
                "rol": usuario["rol"],
            },
        }

    # ------------------------------------------------------------------
    def refrescar(self, token_refresco: str, ip: str, user_agent: str) -> dict:
        """Emite un nuevo token de acceso a partir de uno de refresco válido."""
        try:
            datos = decodificar_token(token_refresco, "refresco")
        except Exception as exc:  # TokenInvalidoError
            raise AutenticacionError("La sesión expiró. Inicia sesión de nuevo.") from exc

        usuario = self._usuario_por_id(int(datos["sub"]))
        if usuario is None or not int(usuario["activo"]):
            raise AutenticacionError("La cuenta ya no está disponible.")

        acceso = crear_token_acceso(usuario)
        nuevo = decodificar_token(acceso, "acceso")
        expira = datetime.fromtimestamp(nuevo["exp"], tz=timezone.utc).replace(tzinfo=None)
        self._repositorio.crear_sesion(
            jti=nuevo["jti"], usuario_id=usuario["id"],
            expira_en=expira.strftime("%Y-%m-%d %H:%M:%S"), ip=ip, user_agent=user_agent,
        )
        return {"token_acceso": acceso}

    # ------------------------------------------------------------------
    def cerrar_sesion(self, jti: str, usuario_id: int, ip: str) -> None:
        self._repositorio.revocar_sesion(jti)
        self._repositorio.registrar_auditoria(usuario_id, "LOGOUT", "Cierre de sesión", ip)

    # ------------------------------------------------------------------
    def _usuario_por_id(self, usuario_id: int) -> dict | None:
        for usuario in self._repositorio.listar_usuarios():
            if int(usuario["id"]) == usuario_id:
                return self._repositorio.buscar_usuario_por_correo(usuario["correo"])
        return None

    @staticmethod
    def _espera_progresiva(correo: str) -> None:
        """Retardo aleatorio creciente para dificultar la fuerza bruta."""
        base = min(
            configuracion.segundos_bloqueo_max,
            configuracion.segundos_bloqueo_min + random.random() * 2,
        )
        time.sleep(base * random.uniform(0.6, 1.0))
