/* =====================================================================
   Panel administrativo — lógica del frontend.
   Consume la API REST protegida con JWT (en cookie HttpOnly). Si la API
   responde 401, cierra la sesión y vuelve al login.
   ===================================================================== */
"use strict";

const API = "/api";

const VISTAS = {
  tablero: { titulo: "Tablero", sub: "Indicadores generales de la operación" },
  flota: { titulo: "Flota", sub: "Vehículos, transportistas y categorías" },
  operacion: { titulo: "Nueva operación", sub: "Clasifica la ruta y genera la documentación con el Factory Method" },
  historial: { titulo: "Historial", sub: "Operaciones registradas en la base de datos" },
  navieras: { titulo: "Navieras", sub: "Compañías navieras por puerto habilitado" },
  administracion: { titulo: "Administración", sub: "Usuarios, intentos de acceso y auditoría" },
};

const estado = { vehiculos: [], usuario: null };

// ------------------------------- Utilidades -------------------------------
const $ = (id) => document.getElementById(id);

const dinero = (v) => "$" + new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(v);

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function mostrarAviso(mensaje, tipo = "info") {
  const aviso = $("aviso");
  aviso.className = `aviso ${tipo}`;
  aviso.textContent = mensaje;
  aviso.classList.remove("oculto");
  clearTimeout(mostrarAviso._t);
  mostrarAviso._t = setTimeout(() => aviso.classList.add("oculto"), 6000);
}

function marcarServidor(ok, texto) {
  const el = $("estado-servidor");
  el.className = `estado ${ok ? "ok" : "error"}`;
  el.innerHTML = `<i></i> ${escapar(texto)}`;
}

/** Petición a la API con manejo central de la sesión expirada. */
async function pedir(ruta, opciones = {}) {
  const respuesta = await fetch(API + ruta, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  if (respuesta.status === 401) {
    window.location.replace("/?sesion=expirada");
    throw new Error("Sesión expirada");
  }
  const cuerpo = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    throw new Error(typeof cuerpo.detail === "string" ? cuerpo.detail : "Error del servidor.");
  }
  return cuerpo;
}

const pastillaVehiculo = (tipo) => {
  const clase = tipo === "TURBO" ? "turbo" : tipo === "CAMION SENCILLO" ? "sencillo" : "tracto";
  return `<span class="pastilla ${clase}">${escapar(tipo)}</span>`;
};

// -------------------------------- Navegación --------------------------------
function cambiarVista(nombre) {
  document.querySelectorAll(".menu-item").forEach((b) =>
    b.classList.toggle("activo", b.dataset.vista === nombre)
  );
  document.querySelectorAll(".vista").forEach((v) =>
    v.classList.toggle("oculto", v.id !== `vista-${nombre}`)
  );
  $("encabezado-titulo").textContent = VISTAS[nombre].titulo;
  $("encabezado-sub").textContent = VISTAS[nombre].sub;

  if (nombre === "tablero") cargarTablero();
  if (nombre === "flota") cargarFlota();
  if (nombre === "historial") cargarHistorial();
  if (nombre === "navieras") cargarNavieras();
  if (nombre === "administracion") cargarAdministracion();
}

// -------------------------------- Tablero --------------------------------
function pintarBarras(contenedor, datos, colores) {
  const maximo = Math.max(1, ...Object.values(datos));
  contenedor.innerHTML = Object.entries(datos)
    .map(([etiqueta, valor], i) => {
      const ancho = Math.round((valor / maximo) * 100);
      return `<div class="barra-fila">
          <span>${escapar(etiqueta)}</span>
          <div class="barra ${colores[i % colores.length]}"><span style="width:${ancho}%"></span></div>
          <span class="barra-valor">${valor}</span>
        </div>`;
    })
    .join("");
}

async function cargarTablero() {
  try {
    const d = await pedir("/resumen");
    $("kpi-vehiculos").textContent = d.total_vehiculos;
    $("kpi-operaciones").textContent = d.total_operaciones;
    $("kpi-internacionales").textContent = d.operaciones_internacionales;
    $("kpi-facturado").textContent = d.facturado_total_formato;
    pintarBarras($("grafico-flota"), d.por_tipo_vehiculo, ["verde", "", "azul"]);
    pintarBarras($("grafico-operaciones"), d.por_tipo_operacion, ["verde", "azul", "morado"]);
    $("puertos-habilitados").textContent = "Puertos habilitados: " + d.puertos_habilitados.join(" · ");
    marcarServidor(true, "Servidor conectado");
  } catch (e) {
    marcarServidor(false, "Sin conexión");
  }
}

// --------------------------------- Flota ---------------------------------
async function cargarFlota(forzar = false) {
  if (forzar || !estado.vehiculos.length) estado.vehiculos = await pedir("/vehiculos");
  pintarFlota();
}

function pintarFlota() {
  const texto = $("filtro-flota").value.trim().toLowerCase();
  const tipo = $("filtro-tipo-vehiculo").value;
  const filas = estado.vehiculos
    .filter((v) => !tipo || v.tipo_vehiculo === tipo)
    .filter((v) => !texto || [v.placa, v.nombre, v.cedula].some((c) => String(c).toLowerCase().includes(texto)))
    .map((v) => `<tr>
        <td class="placa">${escapar(v.placa)}</td>
        <td>${pastillaVehiculo(v.tipo_vehiculo)}</td>
        <td>${v.capacidad_toneladas.toFixed(1)} t</td>
        <td>${escapar(v.tarifa_base_km_formato)}/km</td>
        <td>${escapar(v.nombre)}</td><td>${escapar(v.cedula)}</td>
        <td>${escapar(v.telefono)}</td><td>${escapar(v.licencia)}</td><td>${escapar(v.anio)}</td>
      </tr>`)
    .join("");
  $("cuerpo-flota").innerHTML = filas || `<tr><td colspan="9">Sin resultados.</td></tr>`;
}

function llenarSelectorVehiculos() {
  $("op-placa").innerHTML = estado.vehiculos
    .map((v) => `<option value="${escapar(v.placa)}">${escapar(v.placa)} — ${escapar(v.tipo_vehiculo)} (${v.capacidad_toneladas}t)</option>`)
    .join("");
}

// ---------------------------- Nueva operación ----------------------------
async function clasificarRuta() {
  const origen = $("op-origen").value.trim();
  const destino = $("op-destino").value.trim();
  const caja = $("ruta-clasificada");
  if (!origen || !destino) {
    caja.innerHTML = "Clasificación de la ruta: <em>se completa al elegir origen y destino</em>";
    return;
  }
  try {
    const d = await pedir(`/clasificar?origen=${encodeURIComponent(origen)}&destino=${encodeURIComponent(destino)}`);
    const clase = d.tipo_operacion === "IMPORTACIÓN" ? "imp" : d.tipo_operacion === "EXPORTACIÓN" ? "exp" : "nac";
    caja.innerHTML = `Clasificación de la ruta: <span class="etiqueta ${clase}">${escapar(d.tipo_operacion)}</span> ` +
      (d.es_internacional
        ? "<span class='codigo'>(requiere trámites internacionales y 3 navieras)</span>"
        : "<span class='codigo'>(no requiere importación ni exportación)</span>");
  } catch (e) {
    caja.innerHTML = `<span style="color:var(--rojo)">${escapar(e.message)}</span>`;
  }
}

function cuerpoOperacion(registrar) {
  return {
    placa: $("op-placa").value,
    origen: $("op-origen").value.trim(),
    destino: $("op-destino").value.trim(),
    tipo_carga: $("op-tipo-carga").value,
    peso_toneladas: parseFloat($("op-peso").value || "0"),
    descripcion: $("op-descripcion").value.trim(),
    extradimensionada: $("op-extradimensionada").checked,
    registrar,
  };
}

function pintarResultado(d) {
  const doc = d.documentacion;
  const clase = doc.tipo_operacion === "IMPORTACIÓN" ? "imp" : doc.tipo_operacion === "EXPORTACIÓN" ? "exp" : "nac";
  const navieras = doc.navieras
    ? `<div>
        <h3>Navieras del puerto ${escapar(doc.navieras.puerto)} (3 asignadas)</h3>
        <div class="navieras">
          <div class="naviera-elegida">⚓ ELEGIDA: ${escapar(doc.navieras.elegida.nombre)} [${escapar(doc.navieras.elegida.codigo)}]</div>
          <div class="naviera-alt">${doc.navieras.alternativas.map((n) => `<span>${escapar(n.nombre)} [${escapar(n.codigo)}]</span>`).join("")}</div>
        </div>
      </div>` : "";

  $("resultado-operacion").innerHTML = `
    <div class="resumen-ruta">
      <span class="etiqueta ${clase}">${escapar(doc.tipo_operacion)}</span>
      <span class="pastilla ${d.registrada ? "turbo" : "sencillo"}">
        ${d.registrada ? `Registrada #${d.operacion_id}` : "Simulación (no guardada)"}</span>
    </div>
    <div class="ficha-datos">
      <div class="dato"><p>Creador (Factory Method)</p><p>${escapar(d.creador)}</p></div>
      <div class="dato"><p>Ruta</p><p>${escapar(d.origen)} → ${escapar(d.destino)}</p></div>
      <div class="dato"><p>Distancia</p><p>${Math.round(d.distancia_km).toLocaleString("es-CO")} km</p></div>
      <div class="dato"><p>Vehículo</p><p>${escapar(d.vehiculo.placa)} · ${escapar(d.vehiculo.tipo_vehiculo)}</p></div>
      <div class="dato"><p>Transportista</p><p>${escapar(d.vehiculo.nombre)}</p></div>
      <div class="dato"><p>Cédula</p><p>${escapar(d.vehiculo.cedula)}</p></div>
    </div>
    <div><h3>Documentos generados</h3>
      <ul class="lista-documentos">${doc.documentos.map((x) => `<li>${escapar(x)}</li>`).join("")}</ul></div>
    ${navieras}
    <div class="ficha-datos">
      <div class="dato"><p>Flete terrestre</p><p>${escapar(d.flete_formato)}</p></div>
      <div class="dato"><p>Gestión documental</p><p>${escapar(doc.costo_gestion_formato)}</p></div>
    </div>
    <div class="total-caja"><span>Costo total de la operación</span><strong>${escapar(d.costo_total_formato)}</strong></div>`;
}

async function ejecutarOperacion(registrar) {
  if (!estado.vehiculos.length) await cargarFlota(true);
  const ruta = registrar ? "/operaciones" : "/operaciones/simular";
  try {
    const d = await pedir(ruta, { method: "POST", body: JSON.stringify(cuerpoOperacion(registrar)) });
    pintarResultado(d);
    mostrarAviso(
      registrar ? `Operación registrada con id #${d.operacion_id} (${d.creador}).`
                : `Simulación completada con el creador ${d.creador}.`,
      registrar ? "ok" : "info"
    );
  } catch (e) {
    mostrarAviso(e.message, "error");
  }
}

// ------------------------------- Historial -------------------------------
async function cargarHistorial() {
  const operaciones = await pedir("/operaciones");
  if (!estado.vehiculos.length) await cargarFlota(true);
  const cedulas = new Map(estado.vehiculos.map((v) => [v.placa, `${v.nombre} (${v.cedula})`]));
  $("cuerpo-historial").innerHTML = operaciones
    .map((o) => `<tr>
        <td>#${o.id}</td><td>${escapar(o.fecha)}</td>
        <td class="placa">${escapar(o.placa)}</td><td>${pastillaVehiculo(o.tipo_vehiculo)}</td>
        <td>${escapar(cedulas.get(o.placa) || o.transportista_cedula)}</td>
        <td>${escapar(o.origen)} → ${escapar(o.destino)}</td>
        <td>${escapar(o.carga)}</td><td>${o.peso_toneladas} t</td>
        <td>${escapar(o.naviera || "—")}</td><td>${dinero(o.costo_total)}</td>
      </tr>`)
    .join("") || `<tr><td colspan="10">Todavía no hay operaciones registradas.</td></tr>`;
}

// -------------------------------- Navieras --------------------------------
async function cargarNavieras() {
  const datos = await pedir("/navieras");
  $("rejilla-navieras").innerHTML = Object.entries(datos)
    .map(([puerto, navieras]) => `<article class="tarjeta puerto-card">
        <h2>⚓ ${escapar(puerto)} <span class="pastilla tracto">${navieras.length} navieras</span></h2>
        <ul>${navieras.map((n) => `<li><span>${escapar(n.nombre)}</span><span class="codigo">${escapar(n.codigo)}</span></li>`).join("")}</ul>
      </article>`)
    .join("");
}

// ----------------------------- Administración -----------------------------
async function cargarAdministracion() {
  const [usuarios, intentos, auditoria] = await Promise.all([
    pedir("/admin/usuarios"), pedir("/admin/intentos"), pedir("/admin/auditoria"),
  ]);

  $("cuerpo-usuarios").innerHTML = usuarios
    .map((u) => `<tr>
        <td>${u.id}</td><td>${escapar(u.correo)}</td><td>${escapar(u.nombre)}</td>
        <td><span class="pastilla tracto">${escapar(u.rol)}</span></td>
        <td>${u.activo ? '<span class="pastilla turbo">Activo</span>' : '<span class="pastilla sencillo">Inactivo</span>'}</td>
        <td>${escapar(u.ultimo_acceso || "—")}</td>
      </tr>`)
    .join("");

  $("cuerpo-intentos").innerHTML = intentos
    .map((i) => `<tr>
        <td>${escapar(i.correo)}</td>
        <td>${i.exitoso ? '<span class="pastilla turbo">Éxito</span>' : '<span class="pastilla sencillo">Fallo</span>'}</td>
        <td>${escapar(i.ip)}</td><td>${escapar(i.fecha)}</td>
      </tr>`)
    .join("") || `<tr><td colspan="4">Sin registros.</td></tr>`;

  $("cuerpo-auditoria").innerHTML = auditoria
    .map((a) => `<tr>
        <td>#${a.id}</td><td>${escapar(a.fecha)}</td><td>${escapar(a.usuario)}</td>
        <td><span class="pastilla tracto">${escapar(a.accion)}</span></td>
        <td>${escapar(a.detalle || "—")}</td><td>${escapar(a.ip)}</td>
      </tr>`)
    .join("") || `<tr><td colspan="6">Sin registros.</td></tr>`;
}

// -------------------------------- Sesión --------------------------------
async function pintarUsuario() {
  const u = await pedir("/auth/perfil");
  estado.usuario = u;
  $("usuario-nombre").textContent = u.nombre;
  $("usuario-rol").textContent = u.rol;
  $("usuario-avatar").textContent = u.nombre.charAt(0).toUpperCase();
  if (["ADMINISTRADOR", "AUDITOR"].includes(u.rol)) {
    document.querySelectorAll(".solo-admin").forEach((el) => el.classList.remove("oculto"));
  }
}

async function cerrarSesion() {
  try {
    await pedir("/auth/logout", { method: "POST" });
  } finally {
    window.location.replace("/");
  }
}

// -------------------------------- Arranque --------------------------------
async function iniciar() {
  try {
    await pintarUsuario();
  } catch (_) {
    window.location.replace("/");
    return;
  }

  document.querySelectorAll(".menu-item").forEach((b) =>
    b.addEventListener("click", () => cambiarVista(b.dataset.vista))
  );
  $("filtro-flota").addEventListener("input", pintarFlota);
  $("filtro-tipo-vehiculo").addEventListener("change", pintarFlota);
  $("op-origen").addEventListener("change", clasificarRuta);
  $("op-destino").addEventListener("change", clasificarRuta);
  $("boton-simular").addEventListener("click", () => ejecutarOperacion(false));
  $("boton-refrescar-historial").addEventListener("click", cargarHistorial);
  $("boton-salir").addEventListener("click", cerrarSesion);
  $("formulario-operacion").addEventListener("submit", (e) => {
    e.preventDefault();
    ejecutarOperacion(true);
  });

  try {
    await cargarFlota(true);
    llenarSelectorVehiculos();
    marcarServidor(true, "Servidor conectado");
  } catch (e) {
    marcarServidor(false, "Sin conexión");
  }

  cambiarVista("tablero");
}

document.addEventListener("DOMContentLoaded", iniciar);
