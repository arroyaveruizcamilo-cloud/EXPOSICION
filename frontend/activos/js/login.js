/* =====================================================================
   Lógica de la pantalla de inicio de sesión.
   Envía las credenciales a la API; el token queda en una cookie HttpOnly,
   por lo que JavaScript NUNCA puede leerlo (mitiga el robo por XSS).
   ===================================================================== */
"use strict";

const API = "/api";
let intentosFallidos = 0;

const $ = (id) => document.getElementById(id);

function mostrarAviso(mensaje, tipo = "error") {
  const aviso = $("aviso-login");
  aviso.className = `aviso ${tipo}`;
  aviso.textContent = mensaje;
  aviso.classList.remove("oculto");
}

function ocultarAviso() {
  $("aviso-login").classList.add("oculto");
}

/** Si ya hay sesión válida, salta directo al panel. */
async function verificarSesion() {
  try {
    const respuesta = await fetch(`${API}/auth/perfil`);
    if (respuesta.ok) window.location.replace("/panel");
  } catch (_) {
    /* sin sesión: se queda en el login */
  }
}

async function iniciarSesion(evento) {
  evento.preventDefault();
  ocultarAviso();

  const correo = $("correo").value.trim();
  const contrasena = $("contrasena").value;
  const boton = $("boton-entrar");

  if (!correo || !contrasena) {
    mostrarAviso("Debes completar correo y contraseña.");
    return;
  }

  boton.disabled = true;
  boton.textContent = "Verificando…";

  try {
    const respuesta = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ correo, contrasena }),
    });
    const datos = await respuesta.json().catch(() => ({}));

    if (!respuesta.ok) {
      intentosFallidos += 1;
      $("intentos").textContent = `Intentos fallidos: ${intentosFallidos}`;
      mostrarAviso(datos.detail || "No se pudo iniciar sesión.");
      return;
    }

    mostrarAviso(`Bienvenido, ${datos.usuario.nombre}. Redirigiendo…`, "ok");
    setTimeout(() => window.location.replace("/panel"), 500);
  } catch (error) {
    mostrarAviso("No se pudo conectar con el servidor. ¿Está encendido el backend?");
  } finally {
    boton.disabled = false;
    boton.textContent = "Entrar";
  }
}

function alternarContrasena() {
  const campo = $("contrasena");
  const boton = $("ver-contrasena");
  const visible = campo.type === "text";
  campo.type = visible ? "password" : "text";
  boton.textContent = visible ? "👁" : "🙈";
}

document.addEventListener("DOMContentLoaded", () => {
  $("formulario-login").addEventListener("submit", iniciarSesion);
  $("ver-contrasena").addEventListener("click", alternarContrasena);
  verificarSesion();
});
