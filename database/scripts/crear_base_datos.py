"""Esquema SQL y carga de datos para la base de datos REAL (SQLite).

Este script es la fuente de verdad del esquema y de los datos semilla.
Incluye tanto las tablas del NEGOCIO (transportistas, vehículos, navieras,
rutas, operaciones) como las de SEGURIDAD (usuarios, intentos de acceso,
sesiones y auditoría).

Uso:
    python database/scripts/crear_base_datos.py            # crea si no existe
    python database/scripts/crear_base_datos.py --recrear  # borra y regenera
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from backend.seguridad.seguridad import hash_contrasena  # noqa: E402

RUTA_BASE_DATOS = RAIZ / "database" / "almacen" / "transporte_maquinaria.db"

ESQUEMA = """
PRAGMA foreign_keys = ON;

-- =====================================================================
-- TABLAS DEL NEGOCIO
-- =====================================================================
CREATE TABLE IF NOT EXISTS transportista (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre             TEXT NOT NULL,
    cedula             TEXT NOT NULL UNIQUE CHECK (length(cedula) BETWEEN 8 AND 10),
    telefono           TEXT NOT NULL DEFAULT '',
    categoria_licencia TEXT NOT NULL DEFAULT 'C1'
);

CREATE TABLE IF NOT EXISTS vehiculo (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    placa               TEXT NOT NULL UNIQUE,
    tipo_vehiculo       TEXT NOT NULL CHECK (tipo_vehiculo IN
                          ('TURBO', 'CAMION SENCILLO', 'TRACTOCAMION')),
    transportista_id    INTEGER NOT NULL REFERENCES transportista(id),
    capacidad_toneladas REAL NOT NULL,
    anio                INTEGER NOT NULL,
    activo              INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS naviera (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    codigo TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS naviera_puerto (
    naviera_id INTEGER NOT NULL REFERENCES naviera(id),
    puerto     TEXT NOT NULL,
    PRIMARY KEY (naviera_id, puerto)
);

CREATE TABLE IF NOT EXISTS ruta_km (
    origen       TEXT NOT NULL,
    destino      TEXT NOT NULL,
    distancia_km REAL NOT NULL CHECK (distancia_km > 0),
    PRIMARY KEY (origen, destino)
);

CREATE TABLE IF NOT EXISTS operacion (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha                TEXT NOT NULL,
    placa                TEXT NOT NULL,
    tipo_vehiculo        TEXT NOT NULL,
    transportista_cedula TEXT NOT NULL,
    tipo_operacion       TEXT NOT NULL,
    origen               TEXT NOT NULL,
    destino              TEXT NOT NULL,
    carga                TEXT NOT NULL,
    peso_toneladas       REAL NOT NULL,
    naviera              TEXT,
    costo_total          REAL NOT NULL,
    usuario_id           INTEGER REFERENCES usuario(id)
);

-- =====================================================================
-- TABLAS DE SEGURIDAD Y AUDITORÍA
-- =====================================================================
CREATE TABLE IF NOT EXISTS usuario (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    correo              TEXT NOT NULL UNIQUE,
    nombre              TEXT NOT NULL,
    hash_contrasena     TEXT NOT NULL,
    rol                 TEXT NOT NULL DEFAULT 'OPERADOR'
                          CHECK (rol IN ('ADMINISTRADOR', 'OPERADOR', 'AUDITOR')),
    activo              INTEGER NOT NULL DEFAULT 1,
    intentos_fallidos   INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta     TEXT,
    ultimo_acceso       TEXT,
    creado_en           TEXT NOT NULL DEFAULT (datetime('now')),
    debe_cambiar_clave  INTEGER NOT NULL DEFAULT 0
);

-- Registro de cada intento de inicio de sesión (éxito o fallo).
CREATE TABLE IF NOT EXISTS intento_acceso (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    correo      TEXT NOT NULL,
    exitoso     INTEGER NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    fecha       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Sesiones activas (permite cerrar sesión de forma efectiva y auditar).
CREATE TABLE IF NOT EXISTS sesion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    jti         TEXT NOT NULL UNIQUE,
    usuario_id  INTEGER NOT NULL REFERENCES usuario(id),
    emitida_en  TEXT NOT NULL DEFAULT (datetime('now')),
    expira_en   TEXT NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    revocada    INTEGER NOT NULL DEFAULT 0
);

-- Bitácora de acciones administrativas (quién hizo qué y cuándo).
CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER REFERENCES usuario(id),
    accion      TEXT NOT NULL,
    detalle     TEXT,
    ip          TEXT,
    fecha       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_operacion_placa ON operacion(placa);
CREATE INDEX IF NOT EXISTS idx_intento_correo ON intento_acceso(correo);
CREATE INDEX IF NOT EXISTS idx_sesion_usuario ON sesion(usuario_id);
"""

# ---------------------------------------------------------------------------
# DATOS SEMILLA: transportistas
# ---------------------------------------------------------------------------
TRANSPORTISTAS = [
    ("Luis Fernando Rodríguez Pérez", "80123456", "3001234567", "C1"),
    ("María Elena Ospina Gómez", "43567890", "3019876543", "B1"),
    ("Jhon Alexander Martínez Ruiz", "1023456789", "3104567890", "C2"),
    ("Carlos Andrés Mejía Gutiérrez", "901234567", "3123456789", "C2"),
    ("Sandra Patricia Lozano Díaz", "52890123", "3156789012", "C1"),
    ("Héctor Fabio Vargas Núñez", "79845612", "3182345678", "C3"),
    ("Yina Carolina Peralta Cruz", "1128456734", "3205678901", "C1"),
    ("Édgar Antonio Sandoval Ruiz", "88123456", "3043456789", "C2"),
    ("Diana Marcela Fuentes Ariza", "1015789456", "3167890123", "C1"),
    ("Wilson Emilio Chaparro Palacios", "91234567", "3134567890", "C3"),
]

# ---------------------------------------------------------------------------
# DATOS SEMILLA: vehículos
# ---------------------------------------------------------------------------
VEHICULOS = [
    ("ABC123", "TURBO", 1, 10.0, 2018),
    ("JKP456", "TURBO", 2, 10.0, 2019),
    ("TUR789", "TURBO", 5, 10.0, 2020),
    ("LTM321", "TURBO", 7, 10.0, 2021),
    ("QRS654", "CAMION SENCILLO", 3, 22.0, 2019),
    ("MNO321", "CAMION SENCILLO", 4, 22.0, 2020),
    ("CVB987", "CAMION SENCILLO", 6, 22.0, 2021),
    ("PLK654", "CAMION SENCILLO", 8, 22.0, 2017),
    ("HGD147", "CAMION SENCILLO", 9, 22.0, 2022),
    ("TRK987", "TRACTOCAMION", 3, 60.0, 2020),
    ("EXD741", "TRACTOCAMION", 4, 60.0, 2021),
    ("MAQ852", "TRACTOCAMION", 6, 60.0, 2022),
    ("PES963", "TRACTOCAMION", 10, 60.0, 2023),
    ("LOW159", "TRACTOCAMION", 5, 60.0, 2019),
]

# ---------------------------------------------------------------------------
# DATOS SEMILLA: navieras (3 por puerto habilitado)
# ---------------------------------------------------------------------------
NAVIERAS = [
    ("Maersk", "MAEU"),
    ("CMA CGM", "CMDU"),
    ("MSC", "MSCU"),
    ("Hapag-Lloyd", "HLCU"),
]

NAVIERA_PUERTO = [
    ("Maersk", "CARTAGENA"), ("CMA CGM", "CARTAGENA"), ("MSC", "CARTAGENA"),
    ("Hapag-Lloyd", "BARRANQUILLA"), ("MSC", "BARRANQUILLA"), ("CMA CGM", "BARRANQUILLA"),
    ("CMA CGM", "SANTA MARTA"), ("MSC", "SANTA MARTA"), ("Hapag-Lloyd", "SANTA MARTA"),
    ("Maersk", "BUENAVENTURA"), ("MSC", "BUENAVENTURA"), ("Hapag-Lloyd", "BUENAVENTURA"),
]

RUTAS = [
    ("BOGOTA", "BUCARAMANGA", 397),
    ("BOGOTA", "MEDELLIN", 415),
    ("BOGOTA", "CALI", 462),
    ("BOGOTA", "CUCUTA", 536),
    ("BOGOTA", "IBAGUE", 197),
    ("MEDELLIN", "CALI", 465),
    ("MEDELLIN", "BUCARAMANGA", 546),
    ("CALI", "BUENAVENTURA", 314),
    ("BOGOTA", "BUENAVENTURA", 780),
    ("BOGOTA", "CARTAGENA", 1035),
    ("BOGOTA", "BARRANQUILLA", 1013),
    ("BOGOTA", "SANTA MARTA", 954),
    ("MEDELLIN", "CARTAGENA", 631),
    ("SANTA MARTA", "MEDELLIN", 768),
    ("BARRANQUILLA", "MEDELLIN", 755),
    ("CALI", "CARTAGENA", 1144),
    ("IBAGUE", "BARRANQUILLA", 1010),
    ("BUCARAMANGA", "CUCUTA", 187),
]

# ---------------------------------------------------------------------------
# DATOS SEMILLA: usuarios administrativos
#   Las contraseñas se guardan SIEMPRE como hash bcrypt, nunca en claro.
#   Están pensadas solo para la demostración: cámbialas en producción.
# ---------------------------------------------------------------------------
USUARIOS = [
    ("admin@transmaquinaria.com", "Administrador General", "Admin#2026*Seg", "ADMINISTRADOR"),
    ("operaciones@transmaquinaria.com", "Coordinador de Operaciones", "Oper#2026*Log", "OPERADOR"),
    ("auditoria@transmaquinaria.com", "Auditor Interno", "Audit#2026*Ctl", "AUDITOR"),
]


def crear_base_datos(ruta: Path = RUTA_BASE_DATOS, recrear: bool = False) -> Path:
    """Crea (o recrea) el archivo SQLite y lo carga con los datos semilla."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if recrear and ruta.exists():
        ruta.unlink()

    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(ESQUEMA)
        conexion.execute("PRAGMA foreign_keys = ON")

        # Limpieza idempotente (el orden respeta las claves foráneas).
        for tabla in (
            "auditoria", "sesion", "intento_acceso", "operacion",
            "naviera_puerto", "naviera", "ruta_km", "vehiculo", "transportista", "usuario",
        ):
            conexion.execute(f"DELETE FROM {tabla}")

        conexion.executemany(
            "INSERT INTO transportista (nombre, cedula, telefono, categoria_licencia) VALUES (?, ?, ?, ?)",
            TRANSPORTISTAS,
        )
        conexion.executemany(
            "INSERT INTO vehiculo (placa, tipo_vehiculo, transportista_id, capacidad_toneladas, anio) "
            "VALUES (?, ?, ?, ?, ?)",
            VEHICULOS,
        )
        conexion.executemany("INSERT INTO naviera (nombre, codigo) VALUES (?, ?)", NAVIERAS)
        naviera_ids = {nombre: i for i, nombre in conexion.execute("SELECT id, nombre FROM naviera")}
        conexion.executemany(
            "INSERT INTO naviera_puerto (naviera_id, puerto) VALUES (?, ?)",
            [(naviera_ids[n], p) for n, p in NAVIERA_PUERTO],
        )
        conexion.executemany("INSERT INTO ruta_km (origen, destino, distancia_km) VALUES (?, ?, ?)", RUTAS)

        # Usuarios con contraseña hasheada.
        conexion.executemany(
            "INSERT INTO usuario (correo, nombre, hash_contrasena, rol) VALUES (?, ?, ?, ?)",
            [(correo, nombre, hash_contrasena(clave), rol) for correo, nombre, clave, rol in USUARIOS],
        )

    return ruta


def asegurar_base_datos(ruta: Path = RUTA_BASE_DATOS) -> Path:
    """Crea la base de datos solo si todavía no existe."""
    if not ruta.exists():
        return crear_base_datos(ruta=ruta)
    return ruta


if __name__ == "__main__":
    destino = crear_base_datos(recrear="--recrear" in sys.argv)
    print(f"Base de datos lista en: {destino}")
    print(f"  transportistas : {len(TRANSPORTISTAS)}")
    print(f"  vehículos      : {len(VEHICULOS)}")
    print(f"  navieras       : {len(NAVIERAS)} (3 por puerto habilitado)")
    print(f"  rutas (km)     : {len(RUTAS)}")
    print(f"  usuarios       : {len(USUARIOS)}")
