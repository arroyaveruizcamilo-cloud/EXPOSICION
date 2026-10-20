"""Navieras: producto asociado a las operaciones de importación y exportación.

Reglas del negocio:
  * Solo los puertos colombianos habilitados (Santa Marta, Barranquilla,
    Cartagena y Buenaventura) generan operaciones de importación/exportación.
  * A cada transporte internacional se le ASIGNAN TRES NAVIERAS que operan
    en el puerto; una queda elegida de forma determinística y las otras dos
    se ofrecen como alternativas.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.dominio.interfaces import INaviera


@dataclass(frozen=True)
class Naviera:
    """Compañía naviera que opera en uno o varios puertos colombianos."""

    nombre: str
    codigo: str

    def __str__(self) -> str:
        return f"{self.nombre} [{self.codigo}]"


@dataclass(frozen=True)
class AsignacionNavieras:
    """Resultado de asignar (y ofrecer) las navieras de un puerto."""

    puerto: str
    elegida: Naviera
    alternativas: tuple[Naviera, ...]

    @property
    def todas(self) -> tuple[Naviera, ...]:
        return (self.elegida,) + self.alternativas

    def listar(self) -> str:
        lineas = [f"  -> ELEGIDA: {self.elegida}"]
        for naviera in self.alternativas:
            lineas.append(f"     alternativa: {naviera}")
        return "\n".join(lineas)


class AsignadorNavieras:
    """Asigna las tres navieras disponibles en un puerto al transporte.

    La elección es determinística (depende de la placa), de modo que la
    misma operación siempre arroja el mismo resultado en la presentación.
    """

    MAXIMO_NAVIERAS = 3

    @classmethod
    def asignar(cls, puerto: str, navieras: list[INaviera], placa: str) -> AsignacionNavieras:
        if not navieras:
            raise ValueError(f"No hay navieras registradas para el puerto {puerto}.")
        if len(navieras) < cls.MAXIMO_NAVIERAS:
            raise ValueError(
                f"El puerto {puerto} solo tiene {len(navieras)} navieras registradas; "
                f"se requieren al menos {cls.MAXIMO_NAVIERAS}."
            )

        ordenadas = sorted(navieras, key=lambda n: n.nombre)
        huella = int(hashlib.sha1(placa.encode()).hexdigest(), 16)
        elegida = ordenadas[huella % len(ordenadas)]
        alternativas = tuple(n for n in ordenadas if n.nombre != elegida.nombre)
        return AsignacionNavieras(puerto=puerto, elegida=elegida, alternativas=alternativas)
