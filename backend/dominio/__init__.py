"""Paquete del dominio de transporte (Factory Method).

Módulos:
  * interfaces    -> contratos (Protocol): IVehiculo, IDocumentacionTransporte, INaviera
  * modelos       -> Carga, Transportista, VehiculoBase (abstracta) y subclases
  * documentos    -> PRODUCTOS: DocumentacionNacional / Importacion / Exportacion
  * navieras      -> Naviera y AsignadorNavieras (3 navieras por puerto)
  * creadores     -> CREADORES: TransporteNacional / Importacion / Exportacion
  * repositorio   -> acceso a la base de datos SQLite
"""
