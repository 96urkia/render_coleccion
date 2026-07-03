const API = ""; // mismo origen (FastAPI sirve también el frontend)

const state = {
  sessionId: null,
  biblioteca: null,
  charts: {},
  sigPage: 1,
};

// ---------- utilidades ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function fmtInt(n) { return n === null || n === undefined ? "—" : n.toLocaleString("es-ES"); }

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== "") url.searchParams.set(k, v); });
  const res = await fetch(url);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
  return res.json();
}

async function apiPostForm(path, formData) {
  const res = await fetch(path, { method: "POST", body: formData });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
  return res.json();
}

// ---------- carga inicial: bibliotecas ----------
async function cargarBibliotecas() {
  const bibliotecas = await apiGet("/api/bibliotecas");
  const select = $("#select-biblioteca");
  select.innerHTML = "";
  Object.entries(bibliotecas).forEach(([nombre, poblacion]) => {
    const opt = document.createElement("option");
    opt.value = nombre;
    opt.textContent = nombre;
    opt.dataset.poblacion = poblacion;
    select.appendChild(opt);
  });
  actualizarPoblacionHint();
  select.addEventListener("change", actualizarPoblacionHint);
}

function actualizarPoblacionHint() {
  const select = $("#select-biblioteca");
  const opt = select.options[select.selectedIndex];
  if (opt) $("#poblacion-hint").textContent = `Población atendida: ${Number(opt.dataset.poblacion).toLocaleString("es-ES")} hab.`;
}

// ---------- gestión de archivos ----------
$$("input[type=file]").forEach(input => {
  input.addEventListener("change", () => {
    const label = $(`.file-name[data-for="${input.id}"]`);
    label.textContent = input.files[0] ? input.files[0].name : "Sin archivo";
  });
});

// ---------- analizar ----------
$("#btn-analizar").addEventListener("click", async () => {
  const errorEl = $("#analizar-error");
  errorEl.textContent = "";
  const topo = $("#file-topo").files[0];
  const catalogo = $("#file-catalogo").files[0];
  if (!topo || !catalogo) {
    errorEl.textContent = "Sube los archivos requeridos (listado topográfico y catálogo).";
    return;
  }
  const btn = $("#btn-analizar");
  btn.disabled = true;
  btn.textContent = "Procesando…";
  try {
    const fd = new FormData();
    fd.append("biblioteca", $("#select-biblioteca").value);
    fd.append("tipo_analisis", "Clasificación Mixta Estándar (CDU + Letras)");
    fd.append("num_caracteres", "3");
    fd.append("topo", topo);
    fd.append("catalogo", catalogo);
    if ($("#file-nunca").files[0]) fd.append("nunca", $("#file-nunca").files[0]);
    if ($("#file-mas2").files[0]) fd.append("mas2", $("#file-mas2").files[0]);

    const data = await apiPostForm("/api/analizar", fd);
    state.sessionId = data.session_id;
    state.biblioteca = data.biblioteca;
    localStorage.setItem("gc_session", JSON.stringify({ sessionId: data.session_id, biblioteca: data.biblioteca }));

    $("#bloque-carga").hidden = true;
    $("#bloque-listo").hidden = false;

    renderKpis(data.kpis, data.huerfanos);
    $("#empty-state").hidden = true;
    $("#panel-results").hidden = false;

    await Promise.all([cargarAnalisisGeneral(), cargarAnalisisCdu(), inicializarFiltrosSignatura()]);
  } catch (e) {
    errorEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Analizar fondos";
  }
});

$("#btn-reset").addEventListener("click", () => {
  state.sessionId = null;
  localStorage.removeItem("gc_session");
  $("#bloque-carga").hidden = false;
  $("#bloque-listo").hidden = true;
  $("#panel-results").hidden = true;
  $("#empty-state").hidden = false;
  $$("input[type=file]").forEach(i => (i.value = ""));
  $$(".file-name").forEach(l => (l.textContent = "Sin archivo"));
});

function renderKpis(kpis, huerfanos) {
  const row = $("#kpi-row");
  row.innerHTML = `
    <div class="kpi-card"><div class="kpi-label">Total volúmenes</div><div class="kpi-value">${fmtInt(kpis.total_docs)}</div></div>
    <div class="kpi-card"><div class="kpi-label">Índice de circulación</div><div class="kpi-value">${kpis.pct_prestados}%</div></div>
    <div class="kpi-card"><div class="kpi-label">Edad media del fondo</div><div class="kpi-value">${kpis.edad_media ?? "N/D"}</div></div>
    <div class="kpi-card"><div class="kpi-label">Docs por habitante</div><div class="kpi-value">${kpis.docs_por_habitante}</div></div>
  `;
  $("#huerfanos-note").textContent = huerfanos > 0
    ? `Se han omitido ${huerfanos} registros del topográfico por incoherencias con el catálogo.`
    : "";
}

// ---------- pestañas principales ----------
$$(".guide-tab").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".guide-tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    $$(".tab-panel").forEach(p => (p.hidden = p.dataset.panel !== btn.dataset.tab));
  });
});
function bindSubtabs(navId) {
  $(`#${navId}`).addEventListener("click", e => {
    const btn = e.target.closest(".guide-subtab");
    if (!btn) return;
    const nav = $(`#${navId}`);
    $$(".guide-subtab", nav).forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const container = nav.parentElement;
    $$(".sub-panel", container).forEach(p => (p.hidden = p.dataset.subpanel !== btn.dataset.subtab));
  });
}
bindSubtabs("subtabs-analisis");
bindSubtabs("subtabs-compras");

// ==========================================
// BLOQUE 1A: ANÁLISIS GENERAL
// ==========================================
async function cargarAnalisisGeneral() {
  const data = await apiGet("/api/analisis/general", { session_id: state.sessionId });

  $("#diag-volumen").className = `diag-box ${data.diagnostico_volumen.nivel}`;
  $("#diag-volumen").textContent = data.diagnostico_volumen.texto;
  $("#diag-ratio").className = `diag-box ${data.diagnostico_ratio.nivel}`;
  $("#diag-ratio").textContent = data.diagnostico_ratio.texto;

  const tbody = $("#tabla-macro tbody");
  tbody.innerHTML = data.distribucion_macro.map(r => `<tr><td>${r.seccion}</td><td>${r.pct}%</td></tr>`).join("");

  drawChart("rotacion", "chart-rotacion", "doughnut", {
    labels: data.rotacion.map(r => r.estado),
    datasets: [{ data: data.rotacion.map(r => r.cantidad), backgroundColor: ["#2F5233", "#B08D3E", "#A23B2E"] }],
  });

  drawChart("cronologia", "chart-cronologia", "bar", {
    labels: data.cronologia.labels,
    datasets: [{ label: "Volúmenes", data: data.cronologia.counts, backgroundColor: "#3E6B8A" }],
  }, { scales: { x: { ticks: { maxRotation: 60, minRotation: 60 } } } });
}

// ==========================================
// BLOQUE 1B: ANÁLISIS POR CDU
// ==========================================
async function cargarAnalisisCdu() {
  const data = await apiGet("/api/analisis/cdu", { session_id: state.sessionId });
  renderCduBlock(data.adultos, "chart-cdu-adultos", "tabla-cdu-adultos", "cduAdultos", "#3E6B8A");
  renderCduBlock(data.infantil, "chart-cdu-infantil", "tabla-cdu-infantil", "cduInfantil", "#7B5EA7");
}

function renderCduBlock(rows, canvasId, tableId, chartKey, color) {
  drawChart(chartKey, canvasId, "bar", {
    labels: rows.map(r => r.categoria),
    datasets: [{ label: "Volúmenes", data: rows.map(r => r.volumenes), backgroundColor: color }],
  }, { scales: { x: { ticks: { maxRotation: 55, minRotation: 55 } } } });

  const tbody = $(`#${tableId} tbody`);
  tbody.innerHTML = rows.length
    ? rows.map(r => `<tr><td>${r.categoria}</td><td>${fmtInt(r.volumenes)}</td><td>${r.pct_uso}%</td><td>${r.anio_medio}</td></tr>`).join("")
    : `<tr><td colspan="4">Sin datos suficientes.</td></tr>`;
}

// ==========================================
// BLOQUE 1C: ANÁLISIS POR SIGNATURA
// ==========================================
async function inicializarFiltrosSignatura() {
  state.sigPage = 1;
  await cargarOpcionesSignatura();
  await cargarTablaSignatura();
}

async function cargarOpcionesSignatura() {
  const seccion = $(".seg-btn.active", $("#filtro-seccion")).dataset.val;
  const categoria = $("#select-categoria-sig").value || "Todas";
  const data = await apiGet("/api/analisis/signatura/opciones", { session_id: state.sessionId, seccion, categoria });

  const selCat = $("#select-categoria-sig");
  const catActual = selCat.value;
  selCat.innerHTML = `<option value="Todas">Todas las categorías</option>` +
    data.categorias.map(c => `<option value="${c}">${c}</option>`).join("");
  if (data.categorias.includes(catActual)) selCat.value = catActual;

  const selSub = $("#select-sub-sig");
  selSub.innerHTML = `<option value="Todas">Todas las sub-signaturas</option>` +
    data.subsignaturas.map(c => `<option value="${c}">${c}</option>`).join("");
}

async function cargarTablaSignatura() {
  const seccion = $(".seg-btn.active", $("#filtro-seccion")).dataset.val;
  const params = {
    session_id: state.sessionId,
    seccion,
    busqueda: $("#input-busqueda-sig").value,
    categoria: $("#select-categoria-sig").value,
    sub: $("#select-sub-sig").value,
    prestamo: $("#select-prestamo-sig").value,
    page: state.sigPage,
    page_size: 100,
  };
  const data = await apiGet("/api/analisis/signatura", params);

  $("#sig-count").textContent = `Resultados encontrados: ${fmtInt(data.total)} documentos`;
  const tbody = $("#tabla-signatura tbody");
  tbody.innerHTML = data.filas.length
    ? data.filas.map(f => `<tr class="fila-clicable" data-id-sistema="${f.id_sistema}"><td>${f.id_sistema}</td><td>${f.signatura}</td><td>${f.titulo}</td><td>${f.anio ?? "—"}</td><td>${f.categoria}</td><td>${f.prestamos}</td></tr>`).join("")
    : `<tr><td colspan="6">Sin resultados para estos criterios.</td></tr>`;

  $("#resumen-sig").innerHTML = `
    <span>Volúmenes: ${fmtInt(data.resumen.num_volumenes)}</span>
    <span>% préstamos (uso activo): ${data.resumen.pct_prestados}%</span>
    <span>Año medio: ${data.resumen.anio_medio ?? "Sin datos"}</span>
  `;

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  $("#pager-sig").innerHTML = `
    <button id="pager-prev" ${state.sigPage <= 1 ? "disabled" : ""}>← Anterior</button>
    <span>Página ${state.sigPage} de ${totalPages}</span>
    <button id="pager-next" ${state.sigPage >= totalPages ? "disabled" : ""}>Siguiente →</button>
  `;
  $("#pager-prev")?.addEventListener("click", () => { state.sigPage--; cargarTablaSignatura(); });
  $("#pager-next")?.addEventListener("click", () => { state.sigPage++; cargarTablaSignatura(); });
}

$("#filtro-seccion").addEventListener("click", e => {
  const btn = e.target.closest(".seg-btn");
  if (!btn) return;
  $$(".seg-btn", $("#filtro-seccion")).forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  state.sigPage = 1;
  cargarOpcionesSignatura().then(cargarTablaSignatura);
});
$("#select-categoria-sig").addEventListener("change", () => {
  state.sigPage = 1;
  cargarOpcionesSignatura().then(cargarTablaSignatura);
});
["#select-sub-sig", "#select-prestamo-sig"].forEach(sel => {
  $(sel).addEventListener("change", () => { state.sigPage = 1; cargarTablaSignatura(); });
});
let busquedaDebounce;
$("#input-busqueda-sig").addEventListener("input", () => {
  clearTimeout(busquedaDebounce);
  busquedaDebounce = setTimeout(() => { state.sigPage = 1; cargarTablaSignatura(); }, 350);
});

// ==========================================
// BLOQUE 2A: RECOMENDACIONES GENERALES
// ==========================================
let ultimaCsvGen = "";
$("#btn-cargar-gen").addEventListener("click", cargarRecomendacionesGenerales);
async function cargarRecomendacionesGenerales() {
  const limite = $("#input-limite-gen").value || 50;
  const data = await apiGet("/api/recomendaciones/generales", { biblioteca: state.biblioteca, limite });
  const tbody = $("#tabla-rec-gen tbody");
  tbody.innerHTML = data.resultados.length
    ? data.resultados.map(r => `<tr class="fila-clicable" data-id-sistema="${r.id_sistema}"><td>${r.id_sistema}</td><td>${r.titulo}</td><td>${r.autor ?? ""}</td><td>${r.anio ?? ""}</td><td>${r.num_bibliotecas}</td></tr>`).join("")
    : `<tr><td colspan="5">No se encontraron recomendaciones pendientes.</td></tr>`;

  const header = "ID Sistema;Título;Autor;Año;Nº Bibliotecas en Red\n";
  ultimaCsvGen = header + data.resultados.map(r => [r.id_sistema, r.titulo, r.autor, r.anio, r.num_bibliotecas].join(";")).join("\n");
}
$("#btn-csv-gen").addEventListener("click", () => {
  if (!ultimaCsvGen) return;
  const blob = new Blob([ultimaCsvGen], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "sugerencias_generales.csv";
  a.click();
});

// ==========================================
// BLOQUE 2B: RECOMENDACIONES POR CDU
// ==========================================
let seccionCduActiva = "adultos";
$("#filtro-seccion-cdu").addEventListener("click", e => {
  const btn = e.target.closest(".seg-btn");
  if (!btn) return;
  $$(".seg-btn", $("#filtro-seccion-cdu")).forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  seccionCduActiva = btn.dataset.val;
  renderAcordeonCdu();
});
$("#btn-cargar-cdu").addEventListener("click", cargarRecomendacionesCdu);

let ultimaRecCdu = { adultos: {}, infantil: {} };
async function cargarRecomendacionesCdu() {
  const params = {
    biblioteca: state.biblioteca,
    limite_cdu: $("#input-limite-cdu").value || 10,
    anio_minimo: $("#input-anio-cdu").value || 2015,
    busqueda_cdu: $("#input-busqueda-cdu").value,
  };
  ultimaRecCdu = await apiGet("/api/recomendaciones/cdu", params);
  renderAcordeonCdu();
}
function renderAcordeonCdu() {
  const grupo = ultimaRecCdu[seccionCduActiva] || {};
  const cont = $("#acordeon-cdu");
  const claves = Object.keys(grupo);
  if (!claves.length) {
    cont.innerHTML = `<p class="hint">No hay sugerencias para esta sección con los filtros actuales.</p>`;
    return;
  }
  cont.innerHTML = claves.map((k, idx) => {
    const bloque = grupo[k];
    const filas = bloque.items.map(it => `<tr class="fila-clicable" data-id-sistema="${it.id_sistema}"><td>${it.titulo}</td><td>${it.autor ?? ""}</td><td>${it.anio ?? ""}</td><td>${it.cdu ?? ""}</td><td>${it.num_bibliotecas}</td></tr>`).join("");
    return `
      <div class="accordion-item">
        <button class="accordion-head" data-idx="${idx}">${bloque.titulo} (${bloque.items.length} ítems) <span>▾</span></button>
        <div class="accordion-body" hidden>
          <table class="ledger-table">
            <thead><tr><th>Título</th><th>Autor</th><th>Año</th><th>CDU</th><th>Nº bibliotecas</th></tr></thead>
            <tbody>${filas}</tbody>
          </table>
        </div>
      </div>`;
  }).join("");
  $$(".accordion-head", cont).forEach(btn => {
    btn.addEventListener("click", () => {
      const body = btn.nextElementSibling;
      body.hidden = !body.hidden;
    });
  });
}

// ==========================================
// FICHA CATALOGRÁFICA
// ==========================================
function bindFilasClicables(tableId) {
  $(`#${tableId}`).addEventListener("click", e => {
    const fila = e.target.closest("tr.fila-clicable");
    if (!fila) return;
    abrirFicha(fila.dataset.idSistema);
  });
}
bindFilasClicables("tabla-signatura");
bindFilasClicables("tabla-rec-gen");
$("#acordeon-cdu").addEventListener("click", e => {
  const fila = e.target.closest("tr.fila-clicable");
  if (!fila) return;
  abrirFicha(fila.dataset.idSistema);
});

async function abrirFicha(idSistema) {
  if (!idSistema) return;
  const overlay = $("#ficha-overlay");
  const contenido = $("#ficha-contenido");
  contenido.innerHTML = `<p class="hint">Cargando…</p>`;
  overlay.hidden = false;

  try {
    const f = await apiGet(`/api/ficha/${encodeURIComponent(idSistema)}`);
    contenido.innerHTML = renderFicha(f);
  } catch (e) {
    contenido.innerHTML = `<p class="ficha-error">${e.message}</p>`;
  }
}

function renderFicha(f) {
  const linea = (etiqueta, valor) =>
    valor ? `<div class="ficha-linea"><b>${etiqueta}</b><span>${valor}</span></div>` : "";

  const lineaLista = (etiqueta, valores) =>
    valores && valores.length
      ? `<div class="ficha-linea"><b>${etiqueta}</b><ul class="ficha-lista">${valores.map(v => `<li>${v}</li>`).join("")}</ul></div>`
      : "";

  const camposExtra = Object.entries(f.campos || {})
    .map(([etiqueta, valores]) => lineaLista(etiqueta, valores))
    .join("");

  const ejemplares = (f.ejemplares || [])
    .map(ej => `<div class="ficha-signatura-item">${ej.biblioteca ?? ""} · ${ej.seccion ?? ""} · ${ej.signatura ?? "s/sig."}</div>`)
    .join("") || `<p class="hint">Sin ejemplares localizados en la red.</p>`;

  return `
    <p class="ficha-titulo">${f.titulo ?? "Título no disponible"}</p>
    <p class="ficha-autor">${f.autor ?? "Autor desconocido"}</p>
    ${linea("ID sistema", f.id_sistema)}
    ${linea("ISBN", f.isbn)}
    ${linea("Editorial", f.editorial)}
    ${linea("Año", f.anio)}
    ${linea("CDU", f.cdu)}
    ${camposExtra}
    ${lineaLista("Materias", f.materias)}
    <div class="ficha-linea"><b>Localización</b><div>${ejemplares}</div></div>
  `;
}

$("#ficha-close").addEventListener("click", () => { $("#ficha-overlay").hidden = true; });
$("#ficha-overlay").addEventListener("click", e => {
  if (e.target.id === "ficha-overlay") $("#ficha-overlay").hidden = true;
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#ficha-overlay").hidden) $("#ficha-overlay").hidden = true;
});

// ---------- helper de gráficos ----------
function drawChart(key, canvasId, type, data, extraOptions = {}) {
  const ctx = $(`#${canvasId}`);
  if (!ctx) return;
  if (state.charts[key]) state.charts[key].destroy();
  state.charts[key] = new Chart(ctx, {
    type,
    data,
    options: {
      responsive: true,
      plugins: { legend: { display: type === "doughnut" } },
      font: { family: "Public Sans" },
      ...extraOptions,
    },
  });
}

// ---------- arranque ----------
(async function init() {
  await cargarBibliotecas();

  const saved = localStorage.getItem("gc_session");
  if (saved) {
    try {
      const { sessionId, biblioteca } = JSON.parse(saved);
      state.sessionId = sessionId;
      state.biblioteca = biblioteca;
      $("#select-biblioteca").value = biblioteca;
      actualizarPoblacionHint();
      $("#bloque-carga").hidden = true;
      $("#bloque-listo").hidden = false;
      $("#empty-state").hidden = true;
      $("#panel-results").hidden = false;
      await Promise.all([cargarAnalisisGeneral(), cargarAnalisisCdu(), inicializarFiltrosSignatura()]);
      apiGet("/api/analisis/general", { session_id: sessionId }); // valida que la sesión sigue viva
    } catch (e) {
      localStorage.removeItem("gc_session");
      $("#bloque-carga").hidden = false;
      $("#bloque-listo").hidden = true;
    }
  }
})();
