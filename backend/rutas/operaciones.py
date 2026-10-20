"""Rutas del negocio: catálogos, operaciones y administración.

Todas exigen un usuario autenticado (``Depends(usuario_actual)``); las de
administración exigen además rol ``ADMINISTRADOR`` o ``AUDITOR``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.dominio.creadores import PUERTOS_HABILITADOS, clasificar_operacion, crear_operacion
from backend.dominio.documentos import DocumentacionInternacional, DocumentacionTransporte
from backend.dominio.modelos import Carga, TipoCarga, TipoVehiculo, vehiculo_desde_registro
from backend.dominio.repositorio import Repositorio
from backend.seguridad.dependencias import obtener_repositorio, requiere_rol, usuario_actual

router = APIRouter(prefix="/api", tags=["Operaciones"])


def _cop(valor: float) -> str:
    return "$" + f"{valor:,.0f}".replace(",", ".")


def _ip(peticion: Request) -> str:
    return peticion.client.host if peticion.client else "desconocida"


def _vehiculos(repositorio: Repositorio) -> list:
    return [vehiculo_desde_registro(r) for r in repositorio.listar_vehiculos()]


def _vehiculo_por_placa(repositorio: Repositorio, placa: str):
    for vehiculo in _vehiculos(repositorio):
        if vehiculo.placa == placa.strip().upper():
            return vehiculo
    raise HTTPException(status_code=404, detail=f"La placa {placa!r} no existe en la flota.")


def _tipo_carga(valor: str) -> TipoCarga:
    for tipo in TipoCarga:
        if tipo.value.upper() == valor.strip().upper() or tipo.name == valor.strip().upper():
            return tipo
    raise HTTPException(status_code=422, detail=f"Tipo de carga inválido: {valor!r}")


def _serializar_documentacion(documentacion: DocumentacionTransporte) -> dict:
    navieras = None
    if isinstance(documentacion, DocumentacionInternacional):
        asignacion = documentacion.asignacion_navieras
        navieras = {
            "puerto": asignacion.puerto,
            "elegida": {"nombre": asignacion.elegida.nombre, "codigo": asignacion.elegida.codigo},
            "alternativas": [
                {"nombre": n.nombre, "codigo": n.codigo} for n in asignacion.alternativas
            ],
        }
    return {
        "tipo_operacion": documentacion.tipo_operacion,
        "es_internacional": documentacion.es_internacional,
        "documentos": documentacion.documentos_requeridos(),
        "costo_gestion": documentacion.costo_gestion(),
        "costo_gestion_formato": _cop(documentacion.costo_gestion()),
        "navieras": navieras,
    }


def _razon_rechazo(vehiculo, carga: Carga) -> str:
    if vehiculo.puede_transportar(carga):
        return ""
    if carga.es_extradimensionada and vehiculo.tipo_vehiculo is not TipoVehiculo.TRACTOCAMION:
        return "Solo el tractocamión transporta cargas extradimensionadas."
    if carga.tipo is TipoCarga.MAQUINARIA_AMARILLA and vehiculo.tipo_vehiculo is TipoVehiculo.TURBO:
        return "El turbo no está habilitado para maquinaria amarilla."
    if carga.tipo is TipoCarga.MAQUINARIA_AMARILLA and vehiculo.tipo_vehiculo is TipoVehiculo.CAMION_SENCILLO:
        return "El camión sencillo solo mueve maquinaria liviana (≤ 12 t) y no extradimensionada."
    return f"Supera la capacidad del vehículo ({vehiculo.capacidad_toneladas:g} t)."


# ----------------------------------------------------------------------
# Esquemas
# ----------------------------------------------------------------------
class OperacionEntrada(BaseModel):
    placa: str = Field(..., min_length=6, max_length=6, examples=["TRK987"])
    origen: str = Field(..., min_length=2, examples=["Cartagena"])
    destino: str = Field(..., min_length=2, examples=["Bogotá"])
    tipo_carga: str = Field(..., examples=["Maquinaria amarilla"])
    peso_toneladas: float = Field(0.0, ge=0, examples=[42.0])
    descripcion: str = Field("", max_length=200, examples=["Bulldozer importado"])
    extradimensionada: bool = False
    registrar: bool = True


# ----------------------------------------------------------------------
# Catálogos
# ----------------------------------------------------------------------
@router.get("/resumen")
def resumen(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> dict:
    """KPIs del tablero."""
    vehiculos = _vehiculos(repositorio)
    operaciones = repositorio.listar_operaciones()
    internacionales = [o for o in operaciones if o["tipo_operacion"] != "TRANSPORTE NACIONAL"]
    return {
        "total_vehiculos": len(vehiculos),
        "total_operaciones": len(operaciones),
        "operaciones_internacionales": len(internacionales),
        "facturado_total": sum(o["costo_total"] for o in operaciones),
        "facturado_total_formato": _cop(sum(o["costo_total"] for o in operaciones)),
        "por_tipo_vehiculo": {
            tipo.value: sum(1 for v in vehiculos if v.tipo_vehiculo is tipo) for tipo in TipoVehiculo
        },
        "por_tipo_operacion": {
            etiqueta: sum(1 for o in operaciones if o["tipo_operacion"] == etiqueta)
            for etiqueta in ("TRANSPORTE NACIONAL", "IMPORTACIÓN", "EXPORTACIÓN")
        },
        "puertos_habilitados": sorted(PUERTOS_HABILITADOS),
    }


@router.get("/vehiculos")
def listar_vehiculos(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> list[dict]:
    """Flota con nombre, cédula, placa y tipo de vehículo."""
    return [
        {
            "placa": v.placa,
            "tipo_vehiculo": v.tipo_vehiculo.value,
            "capacidad_toneladas": v.capacidad_toneladas,
            "tarifa_base_km": v.tarifa_base_km,
            "tarifa_base_km_formato": _cop(v.tarifa_base_km),
            "anio": v.anio,
            "nombre": v.transportista.nombre,
            "cedula": v.transportista.cedula,
            "telefono": v.transportista.telefono,
            "licencia": v.transportista.categoria_licencia,
        }
        for v in _vehiculos(repositorio)
    ]


@router.get("/navieras")
def listar_navieras(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> dict:
    """Navieras por puerto habilitado."""
    return {
        puerto: [{"nombre": n.nombre, "codigo": n.codigo} for n in repositorio.navieras_del_puerto(puerto)]
        for puerto in sorted(PUERTOS_HABILITADOS)
    }


@router.get("/clasificar")
def clasificar(
    origen: str,
    destino: str,
    _usuario: dict = Depends(usuario_actual),
) -> dict:
    """Clasifica una ruta en NACIONAL / IMPORTACIÓN / EXPORTACIÓN."""
    try:
        tipo = clasificar_operacion(origen, destino)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "origen": origen,
        "destino": destino,
        "tipo_operacion": tipo.value,
        "es_internacional": tipo.value != "TRANSPORTE NACIONAL",
        "puertos_habilitados": sorted(PUERTOS_HABILITADOS),
    }


@router.get("/compatibilidad")
def compatibilidad(
    clase: str,
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> list[dict]:
    """Flota habilitada para una carga (usa el polimorfismo del dominio)."""
    resultado = []
    for vehiculo in _vehiculos(repositorio):
        carga = Carga(
            descripcion="Verificación de compatibilidad",
            tipo=_tipo_carga(clase),
            peso_toneladas=vehiculo.capacidad_toneladas,
            es_extradimensionada="EXTRADIMENSIONADA" in clase.upper(),
        )
        resultado.append(
            {
                "placa": vehiculo.placa,
                "tipo_vehiculo": vehiculo.tipo_vehiculo.value,
                "capacidad_toneladas": vehiculo.capacidad_toneladas,
                "nombre": vehiculo.transportista.nombre,
                "habilitado": vehiculo.puede_transportar(carga),
                "razon": _razon_rechazo(vehiculo, carga),
            }
        )
    return sorted(resultado, key=lambda v: (not v["habilitado"], v["tipo_vehiculo"], v["placa"]))


# ----------------------------------------------------------------------
# Operaciones
# ----------------------------------------------------------------------
@router.get("/operaciones")
def listar_operaciones(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> list[dict]:
    """Historial de operaciones registradas."""
    operaciones = repositorio.listar_operaciones()
    for operacion in operaciones:
        operacion["costo_total_formato"] = _cop(operacion["costo_total"])
    return operaciones


@router.post("/operaciones/simular")
def simular(
    entrada: OperacionEntrada,
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(usuario_actual),
) -> dict:
    """Calcula la operación SIN registrarla."""
    return _resolver(repositorio, entrada, registrar=False, usuario=None)


@router.post("/operaciones", status_code=201)
def ejecutar(
    entrada: OperacionEntrada,
    peticion: Request,
    repositorio: Repositorio = Depends(obtener_repositorio),
    usuario: dict = Depends(usuario_actual),
) -> dict:
    """Ejecuta y registra la operación, dejando rastro en auditoría."""
    resultado = _resolver(repositorio, entrada, registrar=entrada.registrar, usuario=usuario)
    if resultado["registrada"]:
        repositorio.registrar_auditoria(
            usuario["id"],
            "OPERACION_REGISTRADA",
            f"#{resultado['operacion_id']} {resultado['vehiculo']['placa']} "
            f"{resultado['origen']}->{resultado['destino']}",
            _ip(peticion),
        )
    return resultado


def _resolver(repositorio: Repositorio, entrada: OperacionEntrada, registrar: bool, usuario: dict | None) -> dict:
    vehiculo = _vehiculo_por_placa(repositorio, entrada.placa)
    carga = Carga(
        descripcion=entrada.descripcion.strip() or _tipo_carga(entrada.tipo_carga).value,
        tipo=_tipo_carga(entrada.tipo_carga),
        peso_toneladas=entrada.peso_toneladas,
        es_extradimensionada=entrada.extradimensionada,
    )
    try:
        operacion = crear_operacion(
            vehiculo=vehiculo, carga=carga,
            origen=entrada.origen, destino=entrada.destino, repositorio=repositorio,
        )
        resultado = operacion.ejecutar()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    respuesta = {
        "creador": resultado.creador,
        "vehiculo": {
            "placa": vehiculo.placa,
            "tipo_vehiculo": vehiculo.tipo_vehiculo.value,
            "capacidad_toneladas": vehiculo.capacidad_toneladas,
            "nombre": vehiculo.transportista.nombre,
            "cedula": vehiculo.transportista.cedula,
        },
        "carga": {
            "descripcion": carga.descripcion,
            "tipo": carga.tipo.value,
            "peso_toneladas": carga.peso_toneladas,
            "extradimensionada": carga.es_extradimensionada,
        },
        "origen": resultado.origen,
        "destino": resultado.destino,
        "distancia_km": resultado.distancia_km,
        "flete": resultado.flete,
        "flete_formato": _cop(resultado.flete),
        "costo_total": resultado.costo_total,
        "costo_total_formato": _cop(resultado.costo_total),
        "documentacion": _serializar_documentacion(resultado.documentacion),
        "registrada": False,
        "operacion_id": None,
    }
    if registrar:
        respuesta["operacion_id"] = repositorio.registrar_operacion(
            resultado, usuario_id=usuario["id"] if usuario else None
        )
        respuesta["registrada"] = True
    return respuesta


# ----------------------------------------------------------------------
# Administración (solo ADMINISTRADOR / AUDITOR)
# ----------------------------------------------------------------------
@router.get("/admin/usuarios")
def admin_usuarios(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(requiere_rol("ADMINISTRADOR", "AUDITOR")),
) -> list[dict]:
    """Lista de usuarios del sistema administrativo."""
    return repositorio.listar_usuarios()


@router.get("/admin/auditoria")
def admin_auditoria(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(requiere_rol("ADMINISTRADOR", "AUDITOR")),
) -> list[dict]:
    """Bitácora de acciones administrativas."""
    return repositorio.listar_auditoria()


@router.get("/admin/intentos")
def admin_intentos(
    repositorio: Repositorio = Depends(obtener_repositorio),
    _usuario: dict = Depends(requiere_rol("ADMINISTRADOR", "AUDITOR")),
) -> list[dict]:
    """Últimos intentos de inicio de sesión (éxitos y fallos)."""
    return repositorio.listar_intentos()
