"""PRODUCTOS del patrón Factory Method: la documentación de la operación.

Todos los productos implementan la MISMA interfaz
(``IDocumentacionTransporte``) y heredan de la clase abstracta
``DocumentacionTransporte``:

    DocumentacionTransporte (abstracta)
     ├── DocumentacionNacional        -> transporte nacional (SIN importar/exportar)
     └── DocumentacionInternacional (abstracta)
          ├── DocumentacionImportacion -> origen en puerto colombiano
          └── DocumentacionExportacion -> destino en puerto colombiano

El código cliente (y los creadores) solo conocen la interfaz; las clases
concretas se instancian únicamente dentro del Factory Method de cada
subclase creadora.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.dominio.interfaces import IDocumentacionTransporte, IVehiculo
from backend.dominio.modelos import Carga
from backend.dominio.navieras import AsignacionNavieras


def _formato_cop(valor: float) -> str:
    return "$" + f"{valor:,.0f}".replace(",", ".")


class DocumentacionTransporte(ABC):
    """Clase abstracta de todos los productos documentales."""

    def __init__(self, vehiculo: IVehiculo, carga: Carga, origen: str, destino: str) -> None:
        self._vehiculo = vehiculo
        self._carga = carga
        self._origen = origen
        self._destino = destino

    # -- interfaz IDocumentacionTransporte ---------------------------------
    @property
    @abstractmethod
    def tipo_operacion(self) -> str:
        """Nombre del tipo de operación (para reportes)."""

    @property
    def es_internacional(self) -> bool:
        """Por defecto una operación NO es internacional."""
        return False

    @abstractmethod
    def documentos_requeridos(self) -> list[str]:
        """Lista de documentos que se generan para la operación."""

    @abstractmethod
    def costo_gestion(self) -> float:
        """Costo administrativo/aduanero de la documentación."""

    # -- comportamiento común (usa polimorfismo interno) -------------------
    def resumen(self) -> str:
        documentos = "\n".join(f"  - {d}" for d in self.documentos_requeridos())
        return (
            f"TIPO DE OPERACIÓN : {self.tipo_operacion}\n"
            f"RUTA              : {self._origen} -> {self._destino}\n"
            f"VEHÍCULO          : {self._vehiculo.placa} ({self._vehiculo.tipo_vehiculo.value})\n"
            f"CARGA             : {self._carga.descripcion} | {self._carga.peso_toneladas} t"
            f"{' | EXTRADIMENSIONADA' if self._carga.es_extradimensionada else ''}\n"
            f"DOCUMENTOS GENERADOS:\n{documentos}\n"
            f"COSTO DE GESTIÓN  : {_formato_cop(self.costo_gestion())}"
        )


class DocumentacionNacional(DocumentacionTransporte):
    """Transporte nacional: NO requiere trámites de importación ni exportación."""

    COSTO_GESTION = 120_000.0

    @property
    def tipo_operacion(self) -> str:
        return "TRANSPORTE NACIONAL"

    def documentos_requeridos(self) -> list[str]:
        return [
            "Guía de remisión electrónica (GUÍA-E)",
            "Manifiesto de carga terrestre",
            "Póliza de responsabilidad civil extracontractual (RCE)",
            "Certificado SOAT y revisión técnico-mecánica del vehículo",
        ]

    def costo_gestion(self) -> float:
        return self.COSTO_GESTION


class DocumentacionInternacional(DocumentacionTransporte):
    """Base compartida por importación y exportación: incorpora navieras."""

    def __init__(
        self,
        vehiculo: IVehiculo,
        carga: Carga,
        origen: str,
        destino: str,
        asignacion_navieras: AsignacionNavieras,
    ) -> None:
        super().__init__(vehiculo, carga, origen, destino)
        self._asignacion_navieras = asignacion_navieras

    @property
    def es_internacional(self) -> bool:
        return True

    @property
    def asignacion_navieras(self) -> AsignacionNavieras:
        return self._asignacion_navieras

    @property
    def naviera_asignada(self) -> str:
        return str(self._asignacion_navieras.elegida)

    def documentos_requeridos(self) -> list[str]:
        # Documentos comunes a toda operación portuaria internacional.
        return [
            f"Bill of Lading (B/L) emitido por {self._asignacion_navieras.elegida}",
            "Lista de empaque y factura comercial",
            "Manifiesto de carga del buque",
            "Póliza de transporte internacional (RCT/RCO)",
        ]

    def resumen(self) -> str:
        base = super().resumen()
        return (
            f"{base}\nNAVIERAS DEL PUERTO {self._asignacion_navieras.puerto} "
            f"(se asignan 3):\n{self._asignacion_navieras.listar()}"
        )


class DocumentacionImportacion(DocumentacionInternacional):
    """PRODUCTO concreto: el ORIGEN está en un puerto habilitado
    (Santa Marta, Barranquilla, Cartagena o Buenaventura)."""

    COSTO_GESTION = 520_000.0

    @property
    def tipo_operacion(self) -> str:
        return "IMPORTACIÓN"

    def documentos_requeridos(self) -> list[str]:
        return [
            "Declaración de importación (DIAN - formulario VUE)",
            "Orden de embarque y certificado de navegación",
            *super().documentos_requeridos(),
        ]

    def costo_gestion(self) -> float:
        return self.COSTO_GESTION


class DocumentacionExportacion(DocumentacionInternacional):
    """PRODUCTO concreto: el DESTINO está en un puerto habilitado."""

    COSTO_GESTION = 480_000.0

    @property
    def tipo_operacion(self) -> str:
        return "EXPORTACIÓN"

    def documentos_requeridos(self) -> list[str]:
        return [
            "Declaración de exportación (DIAN - formulario VUE)",
            "Certificado de origen",
            *super().documentos_requeridos(),
        ]

    def costo_gestion(self) -> float:
        return self.COSTO_GESTION
