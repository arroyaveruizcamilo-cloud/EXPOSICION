"""Interfaces (Protocol) del dominio del transporte.

Aquí se define el contrato que deben cumplir TODOS los productos del
patrón Factory Method:

    - ``IDocumentacionTransporte``: producto creado por el Factory Method.
    - ``IVehiculo``: cualquier vehículo de la flota.
    - ``INaviera``: compañía naviera que opera en los puertos colombianos.

En Python las "interfaces" se modelan con ``typing.Protocol`` (tipado
estructural): una clase cumple la interfaz si implementa sus miembros,
sin necesidad de heredar de ella explícitamente.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # imports solo para el analizador de tipos (evita ciclos)
    from backend.dominio.modelos import Carga, TipoVehiculo


@runtime_checkable
class IVehiculo(Protocol):
    """Contrato común para todos los vehículos de la flota."""

    @property
    def placa(self) -> str: ...

    @property
    def tipo_vehiculo(self) -> "TipoVehiculo": ...

    @property
    def capacidad_toneladas(self) -> float: ...

    def puede_transportar(self, carga: "Carga") -> bool: ...

    def calcular_flete(self, distancia_km: float, carga: "Carga") -> float: ...


@runtime_checkable
class IDocumentacionTransporte(Protocol):
    """Contrato común de los PRODUCTOS creados por el Factory Method.

    Toda operación logística, sea nacional, de importación o de
    exportación, produce un objeto que cumple esta interfaz. El código
    cliente nunca depende de las clases concretas (DocumentacionNacional,
    DocumentacionImportacion, DocumentacionExportacion), solo de aquí.
    """

    @property
    def tipo_operacion(self) -> str: ...

    @property
    def es_internacional(self) -> bool: ...

    def documentos_requeridos(self) -> list[str]: ...

    def costo_gestion(self) -> float: ...

    def resumen(self) -> str: ...


@runtime_checkable
class INaviera(Protocol):
    """Contrato de las navieras que pueden asignarse a un transporte."""

    @property
    def nombre(self) -> str: ...

    @property
    def codigo(self) -> str: ...
