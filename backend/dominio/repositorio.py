"""Acceso a la BASE DE DATOS REAL (SQLite) de la empresa.

Tablas consultadas:
  * ``transportista``  -> nombre, cédula, licencia
  * ``vehiculo``       -> placa, tipo de vehículo (TURBO / CAMION SENCILLO /
                          TRACTOCAMION), capacidad, año y transportista
  * ``naviera`` + ``naviera_puerto`` -> las 3 navieras por puerto
  * ``ruta_km``        -> distancias de referencia entre ciudades/puertos
  * ``operacion``      -> registro histórico de las operaciones ejecutadas
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from backend.dominio.modelos import normalizar_texto
from backend.dominio.navieras import Naviera
from backend.nucleo.configuracion import configuracion

RUTA_BASE_DATOS = configuracion.ruta_base_datos

# Distancia por defecto cuando una ruta no está en la tabla ``ruta_km``.
DISTANCIA_POR_DEFECTO_KM = 600.0


class Repositorio:
    """Repositorio de vehículos, navieras, rutas y operaciones."""

    def __init__(self, ruta_base_datos: Path | str = RUTA_BASE_DATOS) -> None:
        self._ruta = Path(ruta_base_datos)
        if not self._ruta.exists():
            raise FileNotFoundError(
                f"No existe la base de datos en {self._ruta}. "
                "Ejecuta primero: python database/crear_base_datos.py"
            )

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        conexion = sqlite3.connect(self._ruta)
        conexion.row_factory = sqlite3.Row
        try:
            yield conexion
            conexion.commit()
        finally:
            conexion.close()

    # ------------------------------------------------------------------
    # Vehículos / transportistas
    # ------------------------------------------------------------------
    def listar_vehiculos(self) -> list[dict]:
        """Devuelve la flota activa con sus transportistas (nombre y cédula)."""
        with self._conexion() as conexion:
            filas = conexion.execute(
                """
                SELECT v.placa,
                       v.tipo_vehiculo,
                       v.capacidad_toneladas,
                       v.anio,
                       t.nombre,
                       t.cedula,
                       t.telefono,
                       t.categoria_licencia
                  FROM vehiculo v
                  JOIN transportista t ON t.id = v.transportista_id
                 WHERE v.activo = 1
                 ORDER BY v.tipo_vehiculo, v.placa
                """
            ).fetchall()
        return [dict(fila) for fila in filas]

    def buscar_vehiculo(self, placa: str) -> dict | None:
        for registro in self.listar_vehiculos():
            if registro["placa"] == placa.strip().upper():
                return registro
        return None

    # ------------------------------------------------------------------
    # Navieras por puerto
    # ------------------------------------------------------------------
    def navieras_del_puerto(self, puerto: str) -> list[Naviera]:
        clave = normalizar_texto(puerto)
        with self._conexion() as conexion:
            filas = conexion.execute(
                """
                SELECT n.nombre, n.codigo
                  FROM naviera n
                  JOIN naviera_puerto np ON np.naviera_id = n.id
                 WHERE np.puerto = ?
                 ORDER BY n.nombre
                """,
                (clave,),
            ).fetchall()
        return [Naviera(nombre=f["nombre"], codigo=f["codigo"]) for f in filas]

    # ------------------------------------------------------------------
    # Distancias
    # ------------------------------------------------------------------
    def distancia_km(self, origen: str, destino: str) -> float:
        origen_n, destino_n = normalizar_texto(origen), normalizar_texto(destino)
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT distancia_km FROM ruta_km WHERE origen = ? AND destino = ?",
                (origen_n, destino_n),
            ).fetchone()
            if fila is None:  # se intenta la ruta inversa antes de fallar por defecto.
                fila = conexion.execute(
                    "SELECT distancia_km FROM ruta_km WHERE origen = ? AND destino = ?",
                    (destino_n, origen_n),
                ).fetchone()
        return float(fila["distancia_km"]) if fila is not None else DISTANCIA_POR_DEFECTO_KM

    # ------------------------------------------------------------------
    # Historial de operaciones
    # ------------------------------------------------------------------
    def registrar_operacion(self, resultado: "object", usuario_id: int | None = None) -> int:
        """Persiste un ``ResultadoOperacion`` en la tabla ``operacion``."""
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        naviera = getattr(resultado, "naviera_asignada", None)
        with self._conexion() as conexion:
            cursor = conexion.execute(
                """
                INSERT INTO operacion
                    (fecha, placa, tipo_vehiculo, transportista_cedula, tipo_operacion,
                     origen, destino, carga, peso_toneladas, naviera, costo_total, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fecha,
                    resultado.vehiculo.placa,
                    resultado.vehiculo.tipo_vehiculo.value,
                    resultado.vehiculo.transportista.cedula,
                    resultado.documentacion.tipo_operacion,
                    resultado.origen,
                    resultado.destino,
                    resultado.carga.descripcion,
                    resultado.carga.peso_toneladas,
                    naviera,
                    resultado.costo_total,
                    usuario_id,
                ),
            )
        return int(cursor.lastrowid)

    def listar_operaciones(self) -> list[dict]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT * FROM operacion ORDER BY id DESC"
            ).fetchall()
        return [dict(fila) for fila in filas]

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------
    def buscar_usuario_por_correo(self, correo: str) -> dict | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT * FROM usuario WHERE correo = ?", (correo.strip().lower(),)
            ).fetchone()
        return dict(fila) if fila else None

    def listar_usuarios(self) -> list[dict]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                """
                SELECT id, correo, nombre, rol, activo, intentos_fallidos,
                       bloqueado_hasta, ultimo_acceso, creado_en, debe_cambiar_clave
                  FROM usuario ORDER BY id
                """
            ).fetchall()
        return [dict(fila) for fila in filas]

    def registrar_acceso_exitoso(self, usuario_id: int) -> None:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                "ultimo_acceso = ? WHERE id = ?",
                (fecha, usuario_id),
            )

    def registrar_intento_fallido(self, correo: str, ip: str, user_agent: str, max_intentos: int, minutos_bloqueo: int) -> None:
        """Suma un intento fallido y bloquea la cuenta si supera el máximo."""
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO intento_acceso (correo, exitoso, ip, user_agent) VALUES (?, 0, ?, ?)",
                (correo.strip().lower(), ip, user_agent),
            )
            fila = conexion.execute(
                "SELECT id, intentos_fallidos FROM usuario WHERE correo = ?", (correo.strip().lower(),)
            ).fetchone()
            if fila is not None:
                intentos = int(fila["intentos_fallidos"]) + 1
                bloqueado_hasta = None
                if intentos >= max_intentos:
                    desde = datetime.now() + timedelta(minutes=minutos_bloqueo)
                    bloqueado_hasta = desde.strftime("%Y-%m-%d %H:%M:%S")
                    intentos = 0  # se reinicia el contador tras bloquear
                conexion.execute(
                    "UPDATE usuario SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE id = ?",
                    (intentos, bloqueado_hasta, fila["id"]),
                )

    def registrar_intento_exitoso(self, correo: str, ip: str, user_agent: str) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO intento_acceso (correo, exitoso, ip, user_agent) VALUES (?, 1, ?, ?)",
                (correo.strip().lower(), ip, user_agent),
            )

    # ------------------------------------------------------------------
    # Sesiones
    # ------------------------------------------------------------------
    def crear_sesion(self, jti: str, usuario_id: int, expira_en: str, ip: str, user_agent: str) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO sesion (jti, usuario_id, expira_en, ip, user_agent) VALUES (?, ?, ?, ?, ?)",
                (jti, usuario_id, expira_en, ip, user_agent),
            )

    def revocar_sesion(self, jti: str) -> None:
        with self._conexion() as conexion:
            conexion.execute("UPDATE sesion SET revocada = 1 WHERE jti = ?", (jti,))

    def sesion_activa(self, jti: str) -> bool:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT revocada FROM sesion WHERE jti = ?", (jti,)
            ).fetchone()
        return fila is not None and int(fila["revocada"]) == 0

    def listar_sesiones(self, usuario_id: int) -> list[dict]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT id, emitida_en, expira_en, ip, user_agent, revocada "
                "FROM sesion WHERE usuario_id = ? ORDER BY id DESC LIMIT 20",
                (usuario_id,),
            ).fetchall()
        return [dict(fila) for fila in filas]

    # ------------------------------------------------------------------
    # Auditoría
    # ------------------------------------------------------------------
    def registrar_auditoria(self, usuario_id: int | None, accion: str, detalle: str, ip: str) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO auditoria (usuario_id, accion, detalle, ip) VALUES (?, ?, ?, ?)",
                (usuario_id, accion, detalle, ip),
            )

    def listar_auditoria(self, limite: int = 100) -> list[dict]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                """
                SELECT a.id, a.fecha, a.accion, a.detalle, a.ip,
                       COALESCE(u.correo, '—') AS usuario
                  FROM auditoria a
                  LEFT JOIN usuario u ON u.id = a.usuario_id
                 ORDER BY a.id DESC LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return [dict(fila) for fila in filas]

    def listar_intentos(self, limite: int = 50) -> list[dict]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT * FROM intento_acceso ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
        return [dict(fila) for fila in filas]
