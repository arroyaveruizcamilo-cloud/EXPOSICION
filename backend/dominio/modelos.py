"""Modelos del dominio: cargas, transportistas y vehículos polimórficos.

Se pone énfasis en:
  * ENCAPSULAMIENTO: estado privado (``_placa``, ``_capacidad_toneladas``)
    expuesto solo vía propiedades de solo lectura, con validación.
  * HERENCIA: ``VehiculoBase`` (clase abstracta) -> Turbo, CamionSencillo,
    Tractocamion.
  * POLIMORFISMO: cada subclase decide su propia tarifa y qué cargas puede
    transportar, sin que el cliente conozca su clase concreta.
"""
from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from backend.dominio.interfaces import IVehiculo

# Patrón de placa colombiano: 3 letras + 3 dígitos (ej. ABC123).
_PATRON_PLACA = re.compile(r"^[A-Z]{3}[0-9]{3}$")
_PATRON_CEDULA = re.compile(r"^\d{8,10}$")


def normalizar_texto(texto: str) -> str:
    """Convierte 'Santa Marta' / 'SANTA  marta' / 'Bogotá' en claves
    comparables: 'SANTA MARTA', 'SANTA MARTA', 'BOGOTA'."""
    sin_tildes = unicodedata.normalize("NFD", texto.strip().upper())
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return " ".join(sin_tildes.split())


class TipoVehiculo(Enum):
    """Categorías de la flota: TURBO, CAMIÓN SENCILLO y TRACTOCAMIÓN."""

    TURBO = "TURBO"
    CAMION_SENCILLO = "CAMION SENCILLO"
    TRACTOCAMION = "TRACTOCAMION"

    @property
    def descripcion(self) -> str:
        return {
            TipoVehiculo.TURBO: "Turbo (camión ligero)",
            TipoVehiculo.CAMION_SENCILLO: "Camión sencillo",
            TipoVehiculo.TRACTOCAMION: "Tractocamión (con dolly / lowboy)",
        }[self]


class TipoCarga(Enum):
    """Tipos de carga que maneja la empresa (enfoque del negocio)."""

    MAQUINARIA_AMARILLA = "Maquinaria amarilla"
    REPUESTOS_E_INSUMOS = "Repuestos e insumos"
    VEHICULO_PROPIOS_MEDIOS = "Vehículo por sus propios medios"
    VEHICULO_CARGADO = "Vehículo cargado"


@dataclass(frozen=True)
class Carga:
    """Descripción de lo que se transporta en una operación."""

    descripcion: str
    tipo: TipoCarga
    peso_toneladas: float = 0.0
    es_extradimensionada: bool = False

    def __post_init__(self) -> None:
        if self.peso_toneladas < 0:
            raise ValueError("El peso no puede ser negativo.")


@dataclass(frozen=True)
class Transportista:
    """Persona habilitada para operar un vehículo (nombre y cédula)."""

    nombre: str
    cedula: str
    telefono: str = ""
    categoria_licencia: str = "C1"

    def __post_init__(self) -> None:
        cedula = self.cedula.strip()
        if not _PATRON_CEDULA.match(cedula):
            raise ValueError(f"Cédula inválida: {self.cedula!r} (debe tener 8 a 10 dígitos).")
        if not self.nombre.strip():
            raise ValueError("El nombre del transportista no puede estar vacío.")
        # Congela la cédula ya validada (dataclass frozen + object.__setattr__).
        object.__setattr__(self, "cedula", cedula)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} (CC. {self.cedula})"


class VehiculoBase(ABC):
    """CLASE ABSTRACTA base de toda la flota.

    Encapsula el estado común (placa, transportista, año, capacidad) y
    delega en las subclases el comportamiento variable (tarifa y cargas
    permitidas) mediante polimorfismo.
    """

    # Costo de escolta para cargas extradimensionadas (aplica a toda la flota).
    COSTO_ESCORTA_EXTRADIMENSIONADA = 850_000.0

    def __init__(self, placa: str, transportista: Transportista, anio: int) -> None:
        placa = placa.strip().upper()
        if not _PATRON_PLACA.match(placa):
            raise ValueError(f"Placa inválida: {placa!r} (formato esperado: ABC123).")
        if not 2000 <= anio <= 2100:
            raise ValueError(f"Año inválido: {anio}.")
        self._placa = placa
        self._transportista = transportista
        self._anio = anio
        # La capacidad la define cada subclase (se recalcula aquí para
        # mantenerla encapsulada y de solo lectura).
        self._capacidad_toneladas = self.capacidad_permitida()

    # ------------------------------------------------------------------
    # Propiedades de solo lectura (ENCAPSULAMIENTO)
    # ------------------------------------------------------------------
    @property
    def placa(self) -> str:
        return self._placa

    @property
    def transportista(self) -> Transportista:
        return self._transportista

    @property
    def anio(self) -> int:
        return self._anio

    @property
    def capacidad_toneladas(self) -> float:
        return self._capacidad_toneladas

    # ------------------------------------------------------------------
    # Comportamiento variable definido por cada subclase (POLIMORFISMO)
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def tipo_vehiculo(self) -> TipoVehiculo:
        """Categoría del vehículo."""

    @property
    @abstractmethod
    def tarifa_base_km(self) -> float:
        """Tarifa base en COP por kilómetro."""

    @abstractmethod
    def capacidad_permitida(self) -> float:
        """Capacidad en toneladas propia de cada categoría."""

    @abstractmethod
    def factor_por_tipo_de_carga(self, carga: Carga) -> float:
        """Recargo (0.18 = 18 %) según el tipo de carga."""

    # ------------------------------------------------------------------
    # Comportamiento compartido
    # ------------------------------------------------------------------
    def puede_transportar(self, carga: Carga) -> bool:
        """Regla base: el peso no supera la capacidad del vehículo."""
        return carga.peso_toneladas <= self._capacidad_toneladas

    def calcular_flete(self, distancia_km: float, carga: Carga) -> float:
        """Flete = tarifa/km * km * (1 + recargo) [+ escolta si es extradimensionada]."""
        if distancia_km <= 0:
            raise ValueError("La distancia debe ser positiva.")
        if not self.puede_transportar(carga):
            raise ValueError(
                f"El vehículo {self._placa} ({self.tipo_vehiculo.value}) no puede "
                f"transportar '{carga.descripcion}' ({carga.peso_toneladas} t)."
            )
        flete = self.tarifa_base_km * distancia_km * (1.0 + self.factor_por_tipo_de_carga(carga))
        if carga.es_extradimensionada:
            flete += self.COSTO_ESCORTA_EXTRADIMENSIONADA
        return flete

    def ficha(self) -> str:
        return (
            f"{self._placa} | {self.tipo_vehiculo.value:<15} | "
            f"{self._capacidad_toneladas:>4.1f} t | {self.tarifa_base_km:>7.0f} COP/km | "
            f"{self._transportista.nombre_completo}"
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} placa={self._placa}>"


# ----------------------------------------------------------------------
# SUBCLASES CONCRETAS de la flota
# ----------------------------------------------------------------------
class Turbo(VehiculoBase):
    """Turbo: camión ligero para repuestos, insumos y vehículos menores."""

    TARIFA_KM = 2_800.0
    CAPACIDAD = 10.0
    _RECARGOS = {
        TipoCarga.REPUESTOS_E_INSUMOS: 0.00,
        TipoCarga.VEHICULO_PROPIOS_MEDIOS: 0.02,
        TipoCarga.VEHICULO_CARGADO: 0.08,
        TipoCarga.MAQUINARIA_AMARILLA: 0.00,  # nunca aplica: se rechaza abajo.
    }

    @property
    def tipo_vehiculo(self) -> TipoVehiculo:
        return TipoVehiculo.TURBO

    @property
    def tarifa_base_km(self) -> float:
        return self.TARIFA_KM

    def capacidad_permitida(self) -> float:
        return self.CAPACIDAD

    def factor_por_tipo_de_carga(self, carga: Carga) -> float:
        return self._RECARGOS[carga.tipo]

    def puede_transportar(self, carga: Carga) -> bool:
        # El transporte de maquinaria amarilla NO es un servicio del turbo.
        return carga.tipo is not TipoCarga.MAQUINARIA_AMARILLA and super().puede_transportar(carga)


class CamionSencillo(VehiculoBase):
    """Camión sencillo: repuestos, insumos, vehículos y maquinaria liviana."""

    TARIFA_KM = 5_200.0
    CAPACIDAD = 22.0
    LIMITE_MAQUINARIA_LIVIANA = 12.0  # toneladas
    _RECARGOS = {
        TipoCarga.REPUESTOS_E_INSUMOS: 0.03,
        TipoCarga.VEHICULO_PROPIOS_MEDIOS: 0.02,
        TipoCarga.VEHICULO_CARGADO: 0.10,
        TipoCarga.MAQUINARIA_AMARILLA: 0.12,
    }

    @property
    def tipo_vehiculo(self) -> TipoVehiculo:
        return TipoVehiculo.CAMION_SENCILLO

    @property
    def tarifa_base_km(self) -> float:
        return self.TARIFA_KM

    def capacidad_permitida(self) -> float:
        return self.CAPACIDAD

    def factor_por_tipo_de_carga(self, carga: Carga) -> float:
        return self._RECARGOS[carga.tipo]

    def puede_transportar(self, carga: Carga) -> bool:
        if carga.tipo is TipoCarga.MAQUINARIA_AMARILLA:
            # Solo maquinaria liviana y nunca extradimensionada.
            return (
                carga.peso_toneladas <= self.LIMITE_MAQUINARIA_LIVIANA
                and not carga.es_extradimensionada
                and super().puede_transportar(carga)
            )
        if carga.es_extradimensionada:
            return False
        return super().puede_transportar(carga)


class Tractocamion(VehiculoBase):
    """Tractocamión: maquinaria amarilla pesada y cargas extradimensionadas."""

    TARIFA_KM = 9_500.0
    CAPACIDAD = 60.0
    _RECARGOS = {
        TipoCarga.MAQUINARIA_AMARILLA: 0.18,
        TipoCarga.REPUESTOS_E_INSUMOS: 0.05,
        TipoCarga.VEHICULO_PROPIOS_MEDIOS: 0.03,
        TipoCarga.VEHICULO_CARGADO: 0.12,
    }

    @property
    def tipo_vehiculo(self) -> TipoVehiculo:
        return TipoVehiculo.TRACTOCAMION

    @property
    def tarifa_base_km(self) -> float:
        return self.TARIFA_KM

    def capacidad_permitida(self) -> float:
        return self.CAPACIDAD

    def factor_por_tipo_de_carga(self, carga: Carga) -> float:
        return self._RECARGOS[carga.tipo]


_CLASES_POR_TIPO = {
    TipoVehiculo.TURBO: Turbo,
    TipoVehiculo.CAMION_SENCILLO: CamionSencillo,
    TipoVehiculo.TRACTOCAMION: Tractocamion,
}


def vehiculo_desde_registro(registro: Mapping[str, object]) -> IVehiculo:
    """Construye el vehículo polimórfico correcto a partir de una fila de la
    base de datos, validando la consistencia de la capacidad."""
    try:
        tipo = TipoVehiculo(str(registro["tipo_vehiculo"]).strip().upper())
    except ValueError as exc:
        raise ValueError(f"Tipo de vehículo desconocido: {registro['tipo_vehiculo']!r}") from exc

    clase = _CLASES_POR_TIPO[tipo]
    transportista = Transportista(
        nombre=str(registro["nombre"]),
        cedula=str(registro["cedula"]),
        telefono=str(registro.get("telefono", "") or ""),
        categoria_licencia=str(registro.get("categoria_licencia", "") or "C1"),
    )
    vehiculo = clase(placa=str(registro["placa"]), transportista=transportista, anio=int(registro["anio"]))

    # La base de datos es la fuente de verdad: si algo no cuadra, falla fuerte.
    capacidad_bd = float(registro["capacidad_toneladas"])
    if abs(vehiculo.capacidad_toneladas - capacidad_bd) > 1e-6:
        raise ValueError(
            f"El vehículo {vehiculo.placa} declara {capacidad_bd} t en la base de datos, "
            f"pero la categoría {tipo.value} permite {vehiculo.capacidad_toneladas} t."
        )
    return vehiculo
