# PATRÓN FACTORY METHOD — Transporte de maquinaria amarilla, pesada y extradimensionada

Empresa de transporte terrestre especializada en:

- **Maquinaria amarilla** pesada y **extradimensionada**.
- **Repuestos e insumos**.
- **Vehículos** por sus propios medios y **cargados**.

El proyecto combina **dos cosas**: por un lado implementa el patrón **Factory
Method** (Método de Fábrica) sobre un dominio real de logística con **base de
datos SQLite real**; por otro, ofrece un **panel administrativo web con login
seguro** (FastAPI + HTML/JS).

---

## Estructura del proyecto (backend / frontend / database separados)

```
exposicion/
├── backend/                          # Lógica del servidor (API + dominio)
│   ├── main.py                       # Punto de entrada FastAPI
│   ├── dominio/                      # DOMINIO (patrón Factory Method)
│   │   ├── interfaces.py             #   IVehiculo, IDocumentacionTransporte, INaviera
│   │   ├── modelos.py                #   VehiculoBase (abstracta) + Turbo/Camión/Tractocamión
│   │   ├── documentos.py             #   PRODUCTOS: Nacional / Importación / Exportación
│   │   ├── navieras.py               #   Naviera + asignación de 3 por puerto
│   │   ├── creadores.py              #   CREADORES: Factory Method
│   │   └── repositorio.py            #   Acceso a SQLite
│   ├── nucleo/                       # Configuración y middlewares de seguridad
│   │   ├── configuracion.py
│   │   └── middleware.py             #   Cabeceras de seguridad + rate limiting
│   ├── seguridad/                    # Autenticación y autorización
│   │   ├── seguridad.py              #   bcrypt + JWT + política de contraseñas
│   │   └── dependencias.py           #   Guards de FastAPI (usuario/roles)
│   ├── servicios/
│   │   └── autenticacion.py          #   Login, bloqueo por intentos, sesiones
│   └── rutas/                        # Endpoints HTTP
│       ├── autenticacion.py          #   /api/auth/*
│       └── operaciones.py            #   /api/* (negocio + administración)
│
├── frontend/                         # Interfaz (archivos separados)
│   ├── vistas/
│   │   ├── login.html                #   Pantalla de inicio de sesión
│   │   └── index.html                #   Panel administrativo
│   └── activos/
│       ├── css/estilos.css
│       └── js/{login.js, app.js}
│
├── database/                         # Base de datos y scripts
│   ├── scripts/crear_base_datos.py   #   Esquema SQL + datos semilla
│   └── almacen/transporte_maquinaria.db   # (se genera)
│
└── requirements.txt
```

---

## Cómo ejecutar

```bash
pip install -r requirements.txt

# Levantar el backend (sirve también el frontend)
python -m backend.main
# o bien:
python -m uvicorn backend.main:app --reload --port 8000
```

- **Login:** http://127.0.0.1:8000/
- **Panel:** http://127.0.0.1:8000/panel
- **Documentación de la API (Swagger):** http://127.0.0.1:8000/api/docs

### Credenciales de demostración

| Rol            | Correo                              | Contraseña        |
|----------------|-------------------------------------|-------------------|
| Administrador  | `admin@transmaquinaria.com`         | `Admin#2026*Seg`  |
| Operador       | `operaciones@transmaquinaria.com`   | `Oper#2026*Log`   |
| Auditor        | `auditoria@transmaquinaria.com`     | `Audit#2026*Ctl`  |

> En producción: define `TM_SECRET_KEY`, activa `TM_COOKIE_SEGURA=1` (con HTTPS)
> y **elimina o cambia** estas credenciales de ejemplo.

---

## 1) Login y seguridad

El acceso es **solo con correo y contraseña** (software administrativo, sin
registro público). Medidas implementadas:

| Medida | Cómo se implementa |
|---|---|
| **Contraseñas hasheadas** | `bcrypt` con coste 12; nunca se guardan en texto plano. |
| **Comparación segura** | `bcrypt.checkpw` (tiempo constante) y hashing descartable si el usuario no existe, para evitar *enumeración de usuarios*. |
| **Tokens JWT** | Firmados con HS256, con `exp`/`iat`/`iss`/`jti`; expiración de acceso 30 min y refresco 7 días. |
| **Cookies HttpOnly** | Los tokens viajan en cookies `HttpOnly` + `SameSite=Lax` (no accesibles por JavaScript → mitiga robo por XSS). |
| **Bloqueo por fuerza bruta** | Tras 5 intentos fallidos la cuenta se bloquea 15 min (HTTP 423). |
| **Retardo progresivo** | Pequeña espera aleatoria en cada fallo para frenar ataques automatizados. |
| **Rate limiting** | Límite en memoria por IP, con cubo aparte para el login (15/min). |
| **Revocación de sesión** | Cada token se registra; al hacer logout se marca como revocado y deja de servir. |
| **Autorización por roles** | `ADMINISTRADOR`, `OPERADOR`, `AUDITOR`; las rutas `/api/admin/*` exigen rol. |
| **Política de contraseñas** | Mínimo 10 caracteres con mayúscula, minúscula, número y símbolo. |
| **Cabeceras de seguridad** | CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`. |
| **Auditoría** | Tablas de intentos de acceso, sesiones y bitácora de acciones. |

### Endpoints de autenticación

| Método | Ruta                  | Descripción                                  |
|--------|-----------------------|----------------------------------------------|
| POST   | `/api/auth/login`     | Inicia sesión (correo + contraseña).         |
| POST   | `/api/auth/logout`    | Cierra sesión y revoca el token.             |
| POST   | `/api/auth/refrescar` | Renueva el token de acceso.                  |
| GET    | `/api/auth/perfil`    | Datos del usuario autenticado.               |

---

## 2) Base de datos real (SQLite)

Tablas de **negocio**: `transportista` (nombre, cédula), `vehiculo` (placa, tipo,
capacidad), `naviera` + `naviera_puerto`, `ruta_km`, `operacion`.
Tablas de **seguridad**: `usuario`, `intento_acceso`, `sesion`, `auditoria`.

Datos semilla: 10 transportistas, 14 vehículos (4 turbo / 5 camiones sencillos /
5 tractocamiones), 4 navieras (3 por puerto), 18 rutas y 3 usuarios.

Regenerar:
```bash
python database/scripts/crear_base_datos.py --recrear
```

---

## 3) Reglas de negocio (Factory Method)

Puertos habilitados: **Santa Marta, Barranquilla, Cartagena, Buenaventura**.

- **Origen** en un puerto → **IMPORTACIÓN** (sí requiere trámites; se asignan **3 navieras** del puerto: una elegida + dos alternativas).
- **Destino** en un puerto → **EXPORTACIÓN** (con **3 navieras** del puerto).
- Ruta sin esos puertos → **TRANSPORTE NACIONAL**, que **no** requiere importación ni exportación.

Capacidades: turbo 10 t (no mueve maquinaria amarilla), camión sencillo 22 t
(maquinaria liviana ≤ 12 t, nunca extradimensionada), tractocamión 60 t
(maquinaria pesada y cargas extradimensionadas, con costo de escolta).

### Pilares OOP

| Pilar | Dónde se ve |
|---|---|
| **Encapsulamiento** | Estado privado (`_placa`, `_capacidad_toneladas`) con propiedades de solo lectura y validación. |
| **Herencia** | `VehiculoBase` → Turbo/Camión/Tractocamión; `DocumentacionTransporte` → Internacional → Importación/Exportación; `OperacionLogistica` → los tres creadores. |
| **Polimorfismo** | `puede_transportar()`, `calcular_flete()`, `documentos_requeridos()`, `crear_documentacion()`. |
| **Clases abstractas** | `VehiculoBase`, `DocumentacionTransporte`, `DocumentacionInternacional`, `OperacionLogistica`. |
| **Interfaces** | `typing.Protocol`: `IVehiculo`, `IDocumentacionTransporte`, `INaviera`. |

### El patrón paso a paso

1. Productos con la misma interfaz → `IDocumentacionTransporte`.
2. Factory Method vacío/abstracto → `OperacionLogistica.crear_documentacion()`.
3. Método plantilla `ejecutar()` que usa el producto sin conocer su clase.
4. Subclases creadoras → `TransporteNacional`, `TransporteImportacion`, `TransporteExportacion`.
5. El cliente llama a `crear_operacion(...)`; para añadir un tipo nuevo solo se agrega una subclase creadora.

---

## 4) Panel administrativo

| Vista | Contenido |
|---|---|
| **Tablero** | KPIs, gráficos por categoría y tipo de operación, reglas de negocio. |
| **Flota** | Placa, tipo, capacidad, transportista, cédula… con búsqueda y filtros. |
| **Nueva operación** | Clasifica la ruta en vivo; simula o registra; muestra documentos, 3 navieras y costos. |
| **Historial** | Operaciones guardadas con su transportista, naviera y costo. |
| **Navieras** | Las 3 navieras por puerto habilitado. |
| **Administración** | *(solo ADMINISTRADOR/AUDITOR)* usuarios, intentos de acceso y bitácora. |

---

## Pruebas rápidas con curl

```bash
# 1) Sin sesión -> 401
curl -i http://127.0.0.1:8000/api/vehiculos

# 2) Login (guarda cookies HttpOnly)
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"correo":"admin@transmaquinaria.com","contrasena":"Admin#2026*Seg"}'

# 3) Con sesión -> 200
curl -b cookies.txt http://127.0.0.1:8000/api/resumen

# 4) Logout
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/auth/logout
```
