"""CREADORES del patrón Factory Method.

    OperacionLogistica (clase creadora abstracta)
     ├── TransporteNacional     -> crea DocumentacionNacional
     ├── TransporteImportacion  -> crea DocumentacionImportacion (con navieras)
     └── TransporteExportacion  -> crea DocumentacionExportacion (con navieras)

El Factory Method es ``crear_documentacion()``: está vacío/abstracto en la
clase base y cada subclase creadora decide qué PRODUCTO concreto instanciar.
El método plantilla ``ejecutar()`` usa el producto SIN conocer su clase.

Reglas de negocio (lo pedido en el punto 2):
  * Si el ORIGEN está en Santa Marta, Barranquilla, Cartagena o
    Buenaventura  ->  IMPORTACIÓN (se asignan 3 navieras del puerto).
  * Si el DESTINO está en esos puertos  ->  EXPORTACIÓN (se asignan 3 navieras).
  * Cualquier otra combinación de origen/destino  ->  TRANSPORTE NACIONAL
    (NO requiere importación ni exportación).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from backend.dominio.documentos import (
    DocumentacionExportacion,
    DocumentacionImportacion,
    DocumentacionNacional,
)
from backend.dominio.interfaces import IDocumentacionTransporte, IVehiculo
from backend.dominio.modelos import Carga, normalizar_texto
from backend.dominio.navieras import AsignadorNavieras
from backend.dominio.repositorio import Repositorio

# Puertos colombianos habilitados para importación y exportación.
PUERTOS_HABILITADOS = frozenset(
    {"SANTA MARTA", "BARRANQUILLA", "CARTAGENA", "BUENAVENTURA"}
)


class TipoOperacion(Enum):
    NACIONAL = "TRANSPORTE NACIONAL"
    IMPORTACION = "IMPORTACIÓN"
    EXPORTACION = "EXPORTACIÓN"


def clasificar_operacion(origen: str, destino: str) -> TipoOperacion:
    """Regla central: puerto habilitado como origen = importación;
    como destino = exportación; cualquier otro caso = nacional."""
    origen_n, destino_n = normalizar_texto(origen), normalizar_texto(destino)
    if not origen_n or not destino_n or origen_n == destino_n:
        raise ValueError("El origen y el destino deben ser distintos y no pueden estar vacíos.")
    if origen_n in PUERTOS_HABILITADOS:
        return TipoOperacion.IMPORTACION
    if destino_n in PUERTOS_HABILITADOS:
        return TipoOperacion.EXPORTACION
    return TipoOperacion.NACIONAL


@dataclass(frozen=True)
class ResultadoOperacion:
    """Objeto que recibe el cliente tras ejecutar una operación."""

    vehiculo: IVehiculo
    carga: Carga
    origen: str
    destino: str
    distancia_km: float
    flete: float
    documentacion: IDocumentacionTransporte
    creador: str

    @property
    def costo_total(self) -> float:
        return self.flete + self.documentacion.costo_gestion()

    @property
    def naviera_asignada(self) -> str | None:
        naviera = getattr(self.documentacion, "naviera_asignada", None)
        return naviera


class OperacionLogistica(ABC):
    """CLASE CREADORA abstracta del Factory Method."""

    def __init__(
        self,
        vehiculo: IVehiculo,
        carga: Carga,
        origen: str,
        destino: str,
        repositorio: Repositorio,
    ) -> None:
        if not vehiculo.puede_transportar(carga):
            raise ValueError(
                f"El vehículo {vehiculo.placa} "
                f"({vehiculo.tipo_vehiculo.value}, {vehiculo.capacidad_toneladas} t) "
                f"no está habilitado para la carga '{carga.descripcion}' "
                f"({carga.peso_toneladas} t)."
            )
        self._vehiculo = vehiculo
        self._carga = carga
        self._origen = origen
        self._destino = destino
        self._repositorio = repositorio

    # ------------------------------------------------------------------
    # FACTORY METHOD (vacío/abstracto en la base; implementado en subclases)
    # ------------------------------------------------------------------
    @abstractmethod
    def crear_documentacion(self) -> IDocumentacionTransporte:
        """Crea el producto adecuado para este tipo de operación."""

    # ------------------------------------------------------------------
    # Método plantilla: usa el producto SIN conocer su clase concreta.
    # ------------------------------------------------------------------
    def ejecutar(self) -> ResultadoOperacion:
        documentacion = self.crear_documentacion()
        distancia = self._repositorio.distancia_km(self._origen, self._destino)
        flete = self._vehiculo.calcular_flete(distancia, self._carga)
        return ResultadoOperacion(
            vehiculo=self._vehiculo,
            carga=self._carga,
            origen=normalizar_texto(self._origen),
            destino=normalizar_texto(self._destino),
            distancia_km=distancia,
            flete=flete,
            documentacion=documentacion,
            creador=type(self).__name__,
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


# ----------------------------------------------------------------------
# SUBCLASES CREADORAS CONCRETAS
# ----------------------------------------------------------------------
class TransporteNacional(OperacionLogistica):
    """Operación nacional: NO requiere importación ni exportación."""

    def crear_documentacion(self) -> IDocumentacionTransporte:
        return DocumentacionNacional(
            vehiculo=self._vehiculo,
            carga=self._carga,
            origen=self._origen,
            destino=self._destino,
        )


class TransporteImportacion(OperacionLogistica):
    """El ORIGEN está en un puerto habilitado: se asignan 3 navieras."""

    @property
    def puerto(self) -> str:
        return normalizar_texto(self._origen)

    def crear_documentacion(self) -> IDocumentacionTransporte:
        navieras = self._repositorio.navieras_del_puerto(self.puerto)
        asignacion = AsignadorNavieras.asignar(
            puerto=self.puerto, navieras=navieras, placa=self._vehiculo.placa
        )
        return DocumentacionImportacion(
            vehiculo=self._vehiculo,
            carga=self._carga,
            origen=self._origen,
            destino=self._destino,
            asignacion_navieras=asignacion,
        )


class TransporteExportacion(OperacionLogistica):
    """El DESTINO está en un puerto habilitado: se asignan 3 navieras."""

    @property
    def puerto(self) -> str:
        return normalizar_texto(self._destino)

    def crear_documentacion(self) -> IDocumentacionTransporte:
        navieras = self._repositorio.navieras_del_puerto(self.puerto)
        asignacion = AsignadorNavieras.asignar(
            puerto=self.puerto, navieras=navieras, placa=self._vehiculo.placa
        )
        return DocumentacionExportacion(
            vehiculo=self._vehiculo,
            carga=self._carga,
            origen=self._origen,
            destino=self._destino,
            asignacion_navieras=asignacion,
        )


# ----------------------------------------------------------------------
# Selector de creador (fábrica simple que acompaña al patrón).
# El código cliente pide "una operación"; jamás instancia productos.
# ----------------------------------------------------------------------
_CREADORES = {
    TipoOperacion.NACIONAL: TransporteNacional,
    TipoOperacion.IMPORTACION: TransporteImportacion,
    TipoOperacion.EXPORTACION: TransporteExportacion,
}


def crear_operacion(
    vehiculo: IVehiculo,
    carga: Carga,
    origen: str,
    destino: str,
    repositorio: Repositorio,
) -> OperacionLogistica:
    tipo = clasificar_operacion(origen, destino)
    return _CREADORES[tipo](
        vehiculo=vehiculo, carga=carga, origen=origen, destino=destino, repositorio=repositorio
    )
