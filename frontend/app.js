const API = ""; // mismo origen (FastAPI sirve también el frontend)

const state = {
  sessionId: null,
  biblioteca: null,
  charts: {},
  sigPage: 1,
  lang: localStorage.getItem("gc_lang") || "es",
  // caché de las últimas respuestas de la API, para poder volver a pintarlas
  // en el otro idioma sin tener que volver a pedirlas al servidor
  cache: { kpis: null, huerfanos: null, general: null, cdu: null },
  // orden activo de las tablas de Análisis por CDU: { key, dir }
  sortCdu: { "tabla-cdu-adultos": { key: null, dir: 1 }, "tabla-cdu-infantil": { key: null, dir: 1 } },
};

// ---------- utilidades ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function fmtInt(n) { return n === null || n === undefined ? "—" : n.toLocaleString(state.lang === "eu" ? "eu-ES" : "es-ES"); }

// ==========================================
// i18n — Español / Euskera
// ==========================================
const I18N = {
  es: {
    app_title: "Gestión de la Colección",
    app_subtitle: "Fichero analítico del fondo bibliotecario — Red de Lectura Pública de Navarra",
    ficha01: "Ficha 01",
    seleccion_biblioteca: "Selección de biblioteca",
    centro: "Centro",
    poblacion_hint: "Población atendida: {{n}} hab.",
    carga_listados: "Carga de listados",
    carga_hint: "Sube los ficheros exportados del catálogo (.txt)",
    listado_topo: "Listado topográfico",
    requerido: "requerido",
    catalogo_label: "Catálogo (Formato 1 / Cuerpo 1 / Orden 8)",
    nunca_prestados: "Ejemplares nunca prestados",
    opcional: "opcional",
    mas_prestados: "Ejemplares más prestados",
    analizar_fondos: "Analizar fondos",
    sin_archivo: "Sin archivo",
    datos_cargados: "✓ Datos cargados",
    cambiar_archivos: "Cambiar / volver a subir archivos",
    kpi_total_volumenes: "Total volúmenes",
    kpi_indice_circulacion: "Índice de circulación",
    kpi_edad_media: "Edad media del fondo",
    kpi_docs_hab: "Docs por habitante",
    huerfanos_note: "Se han omitido {{n}} registros del topográfico por incoherencias con el catálogo.",
    tab_analisis: "Análisis de la colección",
    tab_compras: "Recomendaciones de compra",
    subtab_general: "Análisis general",
    subtab_cdu: "Análisis por CDU",
    subtab_signatura: "Análisis por signatura",
    diagnostico_ifla: "Diagnóstico según pautas IFLA",
    distribucion_macro: "Distribución macroscópica",
    col_seccion: "Sección",
    col_distribucion: "Distribución",
    nivel_rotacion: "Nivel de rotación física",
    cronologia_ediciones: "Cronología de ediciones",
    lbl_volumenes: "Volúmenes",
    seccion_adultos: "Sección adultos",
    seccion_infantil: "Sección infantil / juvenil",
    col_categoria_cdu: "Categoría / CDU",
    col_categoria_tejuelo: "Categoría / Tejuelo",
    col_volumenes: "Volúmenes",
    col_pct_uso: "% Uso",
    col_anio_medio: "Año medio",
    todo_fondo: "Todo el fondo",
    solo_adultos: "Solo adultos",
    solo_infantil: "Solo infantil / juvenil",
    buscar_signatura_placeholder: "Buscar por signatura / CDU · admite comodines (*)",
    todos_prestamos: "Todos los préstamos",
    nunca_prestado_0: "Nunca prestado (0)",
    prestamo_estandar_1: "Préstamo estándar (1)",
    alta_demanda_2: "Alta demanda (2)",
    todas_categorias: "Todas las categorías",
    todas_subsignaturas: "Todas las sub-signaturas",
    resumen_label: "Resumen de la selección",
    resumen_no_filtro: "(no es un filtro, solo informa)",
    resumen_volumenes: "Volúmenes: {{n}}",
    resumen_pct_prestados: "% préstamos (uso activo): {{n}}%",
    resumen_anio_medio: "Año medio: {{n}}",
    sin_datos: "Sin datos",
    clic_fila_hint: "Haz clic en una fila para ver la ficha catalográfica del registro (disponible desde el año de corte de la base de datos de red).",
    col_id: "ID",
    col_signatura: "Signatura",
    col_titulo: "Título",
    col_anio: "Año",
    col_categoria: "Categoría",
    col_prestamos: "Préstamos",
    resultados_encontrados: "Resultados encontrados: {{n}} documentos",
    sin_resultados: "Sin resultados para estos criterios.",
    sin_datos_suficientes: "Sin datos suficientes.",
    pager_anterior: "← Anterior",
    pager_siguiente: "Siguiente →",
    pager_pagina: "Página {{a}} de {{b}}",
    rec_generales: "Recomendaciones generales",
    rec_cdu: "Recomendaciones por CDU",
    titulos_populares: "Títulos populares en la red ausentes en tu centro",
    numero_titulos: "Número de títulos:",
    cargar: "Cargar",
    descargar_csv: "Descargar CSV",
    col_autor: "Autor",
    col_num_bibliotecas: "Nº bibliotecas en red",
    cargando: "Cargando…",
    no_recomendaciones: "No se encontraron recomendaciones pendientes.",
    error_cargar_recomendaciones: "No se pudieron cargar las recomendaciones.",
    sugerencias_cdu: "Sugerencias de adquisición por CDU",
    max_subcategoria: "Máx. por subcategoría:",
    anio_minimo: "Año mínimo:",
    filtrar_cdu_placeholder: "Filtrar por CDU · admite comodines (*), ej. 004*",
    cargar_sugerencias: "Cargar sugerencias",
    seccion_adultos_seg: "Sección adultos",
    seccion_infantil_seg: "Sección infantil",
    no_sugerencias: "No hay sugerencias para esta sección con los filtros actuales.",
    n_items: "{{n}} ítems",
    empty_state: "Selecciona tu biblioteca y sube el listado topográfico y el catálogo para empezar el análisis.",
    cerrar_ficha: "Cerrar ficha",
    ficha_catalografica: "Ficha catalográfica",
    ficha_tab_ficha: "Ficha",
    ficha_tab_sucursales: "Sucursales",
    ficha_col_biblioteca: "Biblioteca",
    ficha_col_seccion: "Sección",
    ficha_col_signatura: "Signatura",
    ficha_col_codigo_barras: "Código de barras",
    ficha_sin_ejemplares: "Sin ejemplares localizados en la red.",
    ficha_titulo_no_disponible: "Título no disponible",
    ficha_nota_sistema: "Ficha generada automáticamente a partir del registro MARC de la red.",
    colophon: "Herramienta de gestión de colección · Diseñada para bibliotecas de la Red de Lectura Pública de Navarra",
    error_archivos_requeridos: "Sube los archivos requeridos (listado topográfico y catálogo).",
    procesando: "Procesando…",
    sin_sig: "s/sig.",
    // diagnósticos IFLA (claves generadas por el backend)
    diag_vol_alerta_minimo: "Alerta: suelo mínimo absoluto IFLA es de 2.500 obras. Tienes {{total}}.",
    diag_vol_deficit: "Déficit de fondo: recomendado {{min}}-{{max}}. Tienes {{total}}.",
    diag_vol_extenso: "Fondo extenso: el rango inicial recomendado es {{min}}-{{max}}. Tienes {{total}}.",
    diag_vol_optimo: "Óptimo: volumen adecuado dentro del rango ({{min}}-{{max}}).",
    diag_hab_demasiado_grande: "Colección demasiado grande: {{ratio}} libros/persona (óptimo {{optimo}}, máx. sugerido 3.5).",
    diag_hab_bajo: "Ratio bajo: {{ratio}} doc/hab. (mínimo recomendado {{minimo}}).",
    diag_hab_optimo: "Ratio óptimo: {{ratio}} doc/hab.",
  },
  eu: {
    app_title: "Bildumaren kudeaketa",
    app_subtitle: "Funts bibliotekarioaren fitxa analitikoa — Nafarroako Irakurketa Publikoaren Sarea",
    ficha01: "01 fitxa",
    seleccion_biblioteca: "Liburutegiaren hautaketa",
    centro: "Zentroa",
    poblacion_hint: "Zerbitzatutako biztanleria: {{n}} biztanle.",
    carga_listados: "Zerrenden kargatzea",
    carga_hint: "Igo katalogotik esportatutako fitxategiak (.txt)",
    listado_topo: "Zerrenda topografikoa",
    requerido: "beharrezkoa",
    catalogo_label: "Katalogoa (1 formatua / 1 gorputza / 8 ordena)",
    nunca_prestados: "Inoiz mailegatu gabeko aleak",
    opcional: "aukerakoa",
    mas_prestados: "Gehien mailegatutako aleak",
    analizar_fondos: "Funtsak aztertu",
    sin_archivo: "Fitxategirik ez",
    datos_cargados: "✓ Datuak kargatuta",
    cambiar_archivos: "Aldatu / fitxategiak berriro igo",
    kpi_total_volumenes: "Ale kopurua guztira",
    kpi_indice_circulacion: "Zirkulazio-indizea",
    kpi_edad_media: "Funtsaren batez besteko adina",
    kpi_docs_hab: "Biztanleko dokumentuak",
    huerfanos_note: "Zerrenda topografikoko {{n}} erregistro alde batera utzi dira katalogoarekiko bat ez etortzeagatik.",
    tab_analisis: "Bildumaren azterketa",
    tab_compras: "Erosketa gomendioak",
    subtab_general: "Azterketa orokorra",
    subtab_cdu: "CDUaren araberako azterketa",
    subtab_signatura: "Signaturaren araberako azterketa",
    diagnostico_ifla: "IFLA jarraibideen araberako diagnostikoa",
    distribucion_macro: "Banaketa makroskopikoa",
    col_seccion: "Atala",
    col_distribucion: "Banaketa",
    nivel_rotacion: "Errotazio fisikoaren maila",
    cronologia_ediciones: "Edizioen kronologia",
    lbl_volumenes: "Aleak",
    seccion_adultos: "Helduen atala",
    seccion_infantil: "Haur eta gazte atala",
    col_categoria_cdu: "Kategoria / CDU",
    col_categoria_tejuelo: "Kategoria / Tejuelo",
    col_volumenes: "Aleak",
    col_pct_uso: "% Erabilera",
    col_anio_medio: "Batez best. urtea",
    todo_fondo: "Funts osoa",
    solo_adultos: "Helduak soilik",
    solo_infantil: "Haurrak eta gazteak soilik",
    buscar_signatura_placeholder: "Bilatu signatura / CDUaren arabera · asterisko (*) onartzen du",
    todos_prestamos: "Mailegu guztiak",
    nunca_prestado_0: "Inoiz mailegatu gabea (0)",
    prestamo_estandar_1: "Mailegu estandarra (1)",
    alta_demanda_2: "Eskari handia (2)",
    todas_categorias: "Kategoria guztiak",
    todas_subsignaturas: "Azpi-signatura guztiak",
    resumen_label: "Hautapenaren laburpena",
    resumen_no_filtro: "(ez da iragazkia, informazio hutsa da)",
    resumen_volumenes: "Aleak: {{n}}",
    resumen_pct_prestados: "% maileguak (erabilera aktiboa): {{n}}%",
    resumen_anio_medio: "Batez besteko urtea: {{n}}",
    sin_datos: "Daturik ez",
    clic_fila_hint: "Egin klik errenkada batean erregistroaren fitxa katalografikoa ikusteko (sareko datu-basearen mozketa-urtetik aurrera eskuragarri).",
    col_id: "ID",
    col_signatura: "Signatura",
    col_titulo: "Izenburua",
    col_anio: "Urtea",
    col_categoria: "Kategoria",
    col_prestamos: "Maileguak",
    resultados_encontrados: "Emaitzak aurkituta: {{n}} dokumentu",
    sin_resultados: "Ez dago emaitzarik irizpide hauekin.",
    sin_datos_suficientes: "Ez dago nahikoa daturik.",
    pager_anterior: "← Aurrekoa",
    pager_siguiente: "Hurrengoa →",
    pager_pagina: "{{a}}/{{b}} orria",
    rec_generales: "Gomendio orokorrak",
    rec_cdu: "CDUaren araberako gomendioak",
    titulos_populares: "Sarean ezagunak diren baina zure zentroan ez dauden izenburuak",
    numero_titulos: "Izenburu kopurua:",
    cargar: "Kargatu",
    descargar_csv: "CSV deskargatu",
    col_autor: "Egilea",
    col_num_bibliotecas: "Sareko liburutegi kop.",
    cargando: "Kargatzen…",
    no_recomendaciones: "Ez da gomendio pendienterik aurkitu.",
    error_cargar_recomendaciones: "Ezin izan dira gomendioak kargatu.",
    sugerencias_cdu: "CDUaren araberako erosketa-iradokizunak",
    max_subcategoria: "Azpikategoriako geh.:",
    anio_minimo: "Gutxieneko urtea:",
    filtrar_cdu_placeholder: "Iragazi CDUaren arabera · asterisko (*) onartzen du, adib. 004*",
    cargar_sugerencias: "Iradokizunak kargatu",
    seccion_adultos_seg: "Helduen atala",
    seccion_infantil_seg: "Haurren atala",
    no_sugerencias: "Ez dago iradokizunik atal honetarako uneko iragazkiekin.",
    n_items: "{{n}} elementu",
    empty_state: "Hautatu zure liburutegia eta igo zerrenda topografikoa eta katalogoa azterketa hasteko.",
    cerrar_ficha: "Fitxa itxi",
    ficha_catalografica: "Fitxa katalografikoa",
    ficha_tab_ficha: "Fitxa",
    ficha_tab_sucursales: "Sukurtsalak",
    ficha_col_biblioteca: "Liburutegia",
    ficha_col_seccion: "Atala",
    ficha_col_signatura: "Signatura",
    ficha_col_codigo_barras: "Barra-kodea",
    ficha_sin_ejemplares: "Ez da alerik aurkitu sarean.",
    ficha_titulo_no_disponible: "Izenburua ez dago eskuragarri",
    ficha_nota_sistema: "Fitxa automatikoki sortu da sareko MARC erregistrotik abiatuta.",
    colophon: "Bildumaren kudeaketarako tresna · Nafarroako Irakurketa Publikoaren Sarerako diseinatua",
    error_archivos_requeridos: "Igo beharrezko fitxategiak (zerrenda topografikoa eta katalogoa).",
    procesando: "Prozesatzen…",
    sin_sig: "sig. gabe",
    diag_vol_alerta_minimo: "Alerta: IFLAren gutxieneko muga absolutua 2.500 obra da. Zuk {{total}} dituzu.",
    diag_vol_deficit: "Funts-defizita: gomendatua {{min}}-{{max}}. Zuk {{total}} dituzu.",
    diag_vol_extenso: "Funts zabala: hasierako gomendatutako tartea {{min}}-{{max}} da. Zuk {{total}} dituzu.",
    diag_vol_optimo: "Optimoa: bolumen egokia tartearen barruan ({{min}}-{{max}}).",
    diag_hab_demasiado_grande: "Bilduma handiegia: {{ratio}} liburu/pertsona (optimoa {{optimo}}, geh. gomendatua 3.5).",
    diag_hab_bajo: "Ratio baxua: {{ratio}} dok./biz. (gutxieneko gomendatua {{minimo}}).",
    diag_hab_optimo: "Ratio optimoa: {{ratio}} dok./biz.",
  },
};

function t(key, vars = {}) {
  const dict = I18N[state.lang] || I18N.es;
  let txt = dict[key] ?? I18N.es[key] ?? key;
  Object.entries(vars).forEach(([k, v]) => { txt = txt.replace(new RegExp(`{{${k}}}`, "g"), v); });
  return txt;
}

// vocabulario fijo devuelto por el backend (no son datos del usuario, así que se traducen aquí)
const SECCION_MAP = {
  es: { "Adultos": "Adultos", "Infantil/Juvenil": "Infantil/Juvenil", "Audiovisuales": "Audiovisuales" },
  eu: { "Adultos": "Helduak", "Infantil/Juvenil": "Haurrak/Gazteak", "Audiovisuales": "Ikus-entzunezkoak" },
};
const ESTADO_MAP = {
  es: { "Nunca prestado": "Nunca prestado", "Prestado": "Prestado", "Muy prestado": "Muy prestado" },
  eu: { "Nunca prestado": "Inoiz mailegatu gabea", "Prestado": "Mailegatua", "Muy prestado": "Oso mailegatua" },
};
const MENU_TITULOS_EU = {
  "Ficción": "Fikzioa Helduak (821)", "CDU 0": "CDU 0 · Orokorrak", "CDU 1": "CDU 1 · Filosofia / Psikologia",
  "CDU 2": "CDU 2 · Erlijioa / Teologia", "CDU 3": "CDU 3 · Gizarte Zientziak / Ekonomia",
  "CDU 5": "CDU 5 · Zientzia Hutsak / Naturalak", "CDU 6": "CDU 6 · Zientzia Aplikatuak / Teknologia",
  "CDU 7": "CDU 7 · Arte Ederrak / Kirolak", "CDU 8": "CDU 8 · Hizkuntzalaritza / Literatura",
  "CDU 9": "CDU 9 · Geografia / Historia",
  "I0": "I0 · Bebeteka", "I1": "I1 · 6 urtera arte", "I2": "I2 · 7-9 urte",
  "I3": "I3 · 10-12 urte", "JN": "JN · Gaztea",
  "I CDU 0": "I CDU 0 · Orokorrak", "I CDU 1": "I CDU 1 · Filosofia", "I CDU 2": "I CDU 2 · Erlijioa",
  "I CDU 3": "I CDU 3 · Gizarte Zientziak", "I CDU 4": "I CDU 4 · Hizkuntza", "I CDU 5": "I CDU 5 · Zientzia Hutsak",
  "I CDU 6": "I CDU 6 · Zientzia Aplikatuak", "I CDU 7": "I CDU 7 · Artea / Kirolak",
  "I CDU 8": "I CDU 8 · Literatura", "I CDU 9": "I CDU 9 · Geografia eta Historia",
};
function traducirSeccion(nombre) { return (SECCION_MAP[state.lang] && SECCION_MAP[state.lang][nombre]) || nombre; }
function traducirEstado(nombre) { return (ESTADO_MAP[state.lang] && ESTADO_MAP[state.lang][nombre]) || nombre; }
function traducirMenuTitulo(clave, tituloOriginal) {
  return state.lang === "eu" && MENU_TITULOS_EU[clave] ? MENU_TITULOS_EU[clave] : tituloOriginal;
}

// Construye el texto de un diagnóstico IFLA a partir de la clave estructurada
// que envía el backend; si no hay clave (versión antigua de la API), usa el
// texto en castellano tal cual venga.
function textoDiagnostico(diag) {
  if (!diag) return "";
  if (diag.clave && I18N.es[`diag_${diag.clave}`]) {
    return t(`diag_${diag.clave}`, diag.valores || {});
  }
  return diag.texto || "";
}

function applyStaticTranslations() {
  document.documentElement.lang = state.lang;
  $$("[data-i18n]").forEach(el => {
    // los nodos con hijos (p.ej. <em> anidado) solo deben traducir su primer nodo de texto
    const key = el.dataset.i18n;
    const translated = t(key);
    const hasElementChildren = Array.from(el.childNodes).some(n => n.nodeType === 1);
    if (hasElementChildren) {
      // sustituye solo el primer nodo de texto (antes de los hijos), preserva el resto del markup
      const firstTextNode = Array.from(el.childNodes).find(n => n.nodeType === 3 && n.textContent.trim());
      if (firstTextNode) firstTextNode.textContent = translated + " ";
      const nestedI18n = el.querySelector("[data-i18n]");
      if (nestedI18n && nestedI18n !== el) nestedI18n.textContent = t(nestedI18n.dataset.i18n);
    } else {
      el.textContent = translated;
    }
  });
  $$("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  $$("[data-i18n-aria-label]").forEach(el => { el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel)); });
  $$(".lang-btn").forEach(b => b.classList.toggle("active", b.dataset.lang === state.lang));
}

function setLang(lang) {
  state.lang = lang;
  localStorage.setItem("gc_lang", lang);
  applyStaticTranslations();
  // vuelve a pintar todo el contenido dinámico ya cargado, sin volver a pedirlo al servidor
  if (state.cache.kpis) renderKpis(state.cache.kpis, state.cache.huerfanos);
  if (state.cache.general) renderAnalisisGeneral(state.cache.general);
  if (state.cache.cdu) renderAnalisisCdu(state.cache.cdu);
  if (state.sessionId) cargarOpcionesSignatura().then(cargarTablaSignatura);
  if (typeof ultimaRecCdu !== "undefined" && Object.keys(ultimaRecCdu.adultos || {}).length + Object.keys(ultimaRecCdu.infantil || {}).length > 0) {
    renderAcordeonCdu();
  }
}
$("#lang-switch").addEventListener("click", e => {
  const btn = e.target.closest(".lang-btn");
  if (btn) setLang(btn.dataset.lang);
});

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
  const select = $("#select-biblioteca");
  let bibliotecas;
  try {
    bibliotecas = await apiGet("/api/bibliotecas");
  } catch (e) {
    console.error("No se pudo cargar /api/bibliotecas:", e);
    select.innerHTML = `<option value="">(error al cargar bibliotecas — revisa la consola)</option>`;
    return;
  }
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
  if (opt) $("#poblacion-hint").textContent = t("poblacion_hint", { n: Number(opt.dataset.poblacion).toLocaleString(state.lang === "eu" ? "eu-ES" : "es-ES") });
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
    errorEl.textContent = t("error_archivos_requeridos");
    return;
  }
  const btn = $("#btn-analizar");
  btn.disabled = true;
  btn.textContent = t("procesando");
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
    btn.textContent = t("analizar_fondos");
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
  state.cache.kpis = kpis;
  state.cache.huerfanos = huerfanos;
  const row = $("#kpi-row");
  row.innerHTML = `
    <div class="kpi-card"><div class="kpi-label">${t("kpi_total_volumenes")}</div><div class="kpi-value">${fmtInt(kpis.total_docs)}</div></div>
    <div class="kpi-card"><div class="kpi-label">${t("kpi_indice_circulacion")}</div><div class="kpi-value">${kpis.pct_prestados}%</div></div>
    <div class="kpi-card"><div class="kpi-label">${t("kpi_edad_media")}</div><div class="kpi-value">${kpis.edad_media ?? "N/D"}</div></div>
    <div class="kpi-card"><div class="kpi-label">${t("kpi_docs_hab")}</div><div class="kpi-value">${kpis.docs_por_habitante}</div></div>
  `;
  $("#huerfanos-note").textContent = huerfanos > 0 ? t("huerfanos_note", { n: huerfanos }) : "";
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
  state.cache.general = data;
  renderAnalisisGeneral(data);
}

function renderAnalisisGeneral(data) {
  $("#diag-volumen").className = `diag-box ${data.diagnostico_volumen.nivel}`;
  $("#diag-volumen").textContent = textoDiagnostico(data.diagnostico_volumen);
  $("#diag-ratio").className = `diag-box ${data.diagnostico_ratio.nivel}`;
  $("#diag-ratio").textContent = textoDiagnostico(data.diagnostico_ratio);

  const tbody = $("#tabla-macro tbody");
  tbody.innerHTML = data.distribucion_macro.map(r => `<tr><td>${traducirSeccion(r.seccion)}</td><td>${r.pct}%</td></tr>`).join("");

  const COLOR_ROTACION = {
    "Nunca prestado": CHART_COLORS.rojo,
    "Prestado": CHART_COLORS.oro,
    "Muy prestado": CHART_COLORS.verde,
  };
  drawChart("rotacion", "chart-rotacion", "doughnut", {
    labels: data.rotacion.map(r => traducirEstado(r.estado)),
    datasets: [{ data: data.rotacion.map(r => r.cantidad), backgroundColor: data.rotacion.map(r => COLOR_ROTACION[r.estado] || CHART_COLORS.ciruela) }],
  });

  drawChart("cronologia", "chart-cronologia", "bar", {
    labels: data.cronologia.labels,
    datasets: [{ label: t("lbl_volumenes"), data: data.cronologia.counts, backgroundColor: CHART_COLORS.azulPetroleo }],
  }, { scales: { x: { ticks: { maxRotation: 60, minRotation: 60 } } } });
}

// ==========================================
// BLOQUE 1B: ANÁLISIS POR CDU
// ==========================================
async function cargarAnalisisCdu() {
  const data = await apiGet("/api/analisis/cdu", { session_id: state.sessionId });
  state.cache.cdu = data;
  renderAnalisisCdu(data);
}

function renderAnalisisCdu(data) {
  renderCduBlock(data.adultos, "chart-cdu-adultos", "tabla-cdu-adultos", "cduAdultos", CHART_COLORS.azulPetroleo);
  renderCduBlock(data.infantil, "chart-cdu-infantil", "tabla-cdu-infantil", "cduInfantil", CHART_COLORS.marronCuero);
}

// ---------- degradado de color según % de préstamos ----------
// Cuanto menor es el % de préstamos, más cerca del blanco queda la barra;
// cuanto mayor, más se acerca al color base de la sección. Se normaliza
// dentro del propio conjunto de categorías mostrado, para que el contraste
// sea visible aunque todos los valores absolutos sean bajos.
function hexToRgb(hex) {
  const n = parseInt(hex.replace("#", ""), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}
function mezclarConBlanco(hex, factor) {
  const { r, g, b } = hexToRgb(hex);
  const mix = c => Math.round(255 + (c - 255) * factor);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}
function coloresPorUso(rows, baseHex) {
  const pcts = rows.map(r => Number(r.pct_uso) || 0);
  const min = Math.min(...pcts, 0);
  const max = Math.max(...pcts, 0);
  return rows.map(r => {
    const pct = Number(r.pct_uso) || 0;
    const posicion = max > min ? (pct - min) / (max - min) : 1;
    // suelo de 0.15 para que incluso el valor mínimo se distinga levemente del blanco puro
    const factor = 0.15 + posicion * 0.85;
    return mezclarConBlanco(baseHex, factor);
  });
}

// ---------- tablas ordenables ----------
function ordenarFilas(tableId, rows) {
  const s = state.sortCdu[tableId];
  if (!s || !s.key) return rows;
  return [...rows].sort((a, b) => {
    let av = a[s.key], bv = b[s.key];
    if (typeof av === "string" || typeof bv === "string") {
      return String(av ?? "").localeCompare(String(bv ?? "")) * s.dir;
    }
    return ((av ?? -Infinity) - (bv ?? -Infinity)) * s.dir;
  });
}
function actualizarIndicadoresOrden(tableId) {
  const s = state.sortCdu[tableId];
  $$(`#${tableId} thead th[data-key]`).forEach(th => {
    th.classList.remove("sort-asc", "sort-desc");
    if (s && th.dataset.key === s.key) th.classList.add(s.dir === 1 ? "sort-asc" : "sort-desc");
  });
}
function bindSortableCdu(tableId, canvasId, chartKey, color) {
  $(`#${tableId} thead`).addEventListener("click", e => {
    const th = e.target.closest("th[data-key]");
    if (!th) return;
    const s = state.sortCdu[tableId];
    if (s.key === th.dataset.key) s.dir *= -1; else { s.key = th.dataset.key; s.dir = 1; }
    const rows = tableId === "tabla-cdu-adultos" ? state.cache.cdu?.adultos : state.cache.cdu?.infantil;
    if (rows) renderCduBlock(rows, canvasId, tableId, chartKey, color);
  });
}
bindSortableCdu("tabla-cdu-adultos", "chart-cdu-adultos", "cduAdultos", CHART_COLORS.azulPetroleo);
bindSortableCdu("tabla-cdu-infantil", "chart-cdu-infantil", "cduInfantil", CHART_COLORS.marronCuero);

function renderCduBlock(rowsOriginal, canvasId, tableId, chartKey, color) {
  const rows = ordenarFilas(tableId, rowsOriginal);
  const colores = coloresPorUso(rows, color);

  drawChart(chartKey, canvasId, "bar", {
    labels: rows.map(r => r.categoria),
    datasets: [{ label: t("lbl_volumenes"), data: rows.map(r => r.volumenes), backgroundColor: colores, borderColor: color, borderWidth: 1 }],
  }, { scales: { x: { ticks: { maxRotation: 55, minRotation: 55 } } } });

  const tbody = $(`#${tableId} tbody`);
  tbody.innerHTML = rows.length
    ? rows.map((r, i) => `<tr><td><span class="uso-swatch" style="background:${colores[i]}"></span>${r.categoria}</td><td>${fmtInt(r.volumenes)}</td><td>${r.pct_uso}%</td><td>${r.anio_medio}</td></tr>`).join("")
    : `<tr><td colspan="4">${t("sin_datos_suficientes")}</td></tr>`;

  actualizarIndicadoresOrden(tableId);
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
  selCat.innerHTML = `<option value="Todas">${t("todas_categorias")}</option>` +
    data.categorias.map(c => `<option value="${c}">${c}</option>`).join("");
  if (data.categorias.includes(catActual)) selCat.value = catActual;

  const selSub = $("#select-sub-sig");
  selSub.innerHTML = `<option value="Todas">${t("todas_subsignaturas")}</option>` +
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

  $("#sig-count").textContent = t("resultados_encontrados", { n: fmtInt(data.total) });
  const tbody = $("#tabla-signatura tbody");
  tbody.innerHTML = data.filas.length
    ? data.filas.map(f => `<tr class="fila-clicable" data-id-sistema="${f.id_sistema}"><td>${f.id_sistema}</td><td>${f.signatura}</td><td>${f.titulo}</td><td>${f.anio ?? "—"}</td><td>${f.categoria}</td><td>${f.prestamos}</td></tr>`).join("")
    : `<tr><td colspan="6">${t("sin_resultados")}</td></tr>`;

  $("#resumen-sig").innerHTML = `
    <span>${t("resumen_volumenes", { n: fmtInt(data.resumen.num_volumenes) })}</span>
    <span>${t("resumen_pct_prestados", { n: data.resumen.pct_prestados })}</span>
    <span>${t("resumen_anio_medio", { n: data.resumen.anio_medio ?? t("sin_datos") })}</span>
  `;

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  $("#pager-sig").innerHTML = `
    <button id="pager-prev" ${state.sigPage <= 1 ? "disabled" : ""}>${t("pager_anterior")}</button>
    <span>${t("pager_pagina", { a: state.sigPage, b: totalPages })}</span>
    <button id="pager-next" ${state.sigPage >= totalPages ? "disabled" : ""}>${t("pager_siguiente")}</button>
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
  const btn = $("#btn-cargar-gen");
  const errorBox = $("#rec-gen-error");
  const tbody = $("#tabla-rec-gen tbody");
  errorBox.textContent = "";
  btn.disabled = true;
  const textoOriginal = btn.textContent;
  btn.textContent = t("cargando");
  tbody.innerHTML = `<tr><td colspan="4">${t("cargando")}</td></tr>`;
  try {
    const data = await apiGet("/api/recomendaciones/generales", { biblioteca: state.biblioteca, limite });
    tbody.innerHTML = data.resultados.length
      ? data.resultados.map(r => `<tr class="fila-clicable" data-id-sistema="${r.id_sistema}"><td>${r.titulo}</td><td>${r.autor ?? ""}</td><td>${r.anio ?? ""}</td><td>${r.num_bibliotecas}</td></tr>`).join("")
      : `<tr><td colspan="4">${t("no_recomendaciones")}</td></tr>`;

    const header = "ID Sistema;Título;Autor;Año;Nº Bibliotecas en Red\n";
    ultimaCsvGen = header + data.resultados.map(r => [r.id_sistema, r.titulo, r.autor, r.anio, r.num_bibliotecas].join(";")).join("\n");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4">${t("error_cargar_recomendaciones")}</td></tr>`;
    errorBox.textContent = e.message || t("error_cargar_recomendaciones");
  } finally {
    btn.disabled = false;
    btn.textContent = textoOriginal;
  }
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
    cont.innerHTML = `<p class="hint">${t("no_sugerencias")}</p>`;
    return;
  }
  cont.innerHTML = claves.map((k, idx) => {
    const bloque = grupo[k];
    const filas = bloque.items.map(it => `<tr class="fila-clicable" data-id-sistema="${it.id_sistema}"><td>${it.titulo}</td><td>${it.autor ?? ""}</td><td>${it.anio ?? ""}</td><td>${it.cdu ?? ""}</td><td>${it.num_bibliotecas}</td></tr>`).join("");
    return `
      <div class="accordion-item">
        <button class="accordion-head" data-idx="${idx}">${traducirMenuTitulo(k, bloque.titulo)} (${t("n_items", { n: bloque.items.length })}) <span>▾</span></button>
        <div class="accordion-body" hidden>
          <table class="ledger-table">
            <thead><tr><th>${t("col_titulo")}</th><th>${t("col_autor")}</th><th>${t("col_anio")}</th><th>CDU</th><th>${t("col_num_bibliotecas")}</th></tr></thead>
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
  contenido.innerHTML = `<p class="hint">${t("cargando")}</p>`;
  overlay.hidden = false;
  activarFichaTab("isbd");

  try {
    const f = await apiGet(`/api/ficha/${encodeURIComponent(idSistema)}`);
    contenido.innerHTML = renderFicha(f);
  } catch (e) {
    contenido.innerHTML = `<p class="ficha-error">${e.message}</p>`;
  }
}

function activarFichaTab(tab) {
  $$(".ficha-nav-tab").forEach(b => b.classList.toggle("active", b.dataset.fichaTab === tab));
  $$(".ficha-panel", $("#ficha-contenido")).forEach(p => (p.hidden = p.dataset.fichaPanel !== tab));
}
$("#ficha-nav-tabs").addEventListener("click", e => {
  const btn = e.target.closest(".ficha-nav-tab");
  if (btn) activarFichaTab(btn.dataset.fichaTab);
});

// Construye el párrafo bibliográfico en formato ISBD:
// Título : subtítulo / mención de responsabilidad. — Edición. — Lugar : Editorial, Año.
// Descripción física. — (Serie)
// Notas.
function renderIsbdParrafo(f) {
  const partes = [];

  let linea1 = `<span class="isbd-titulo">${f.titulo ?? t("ficha_titulo_no_disponible")}</span>`;
  if (f.autor) linea1 += ` / ${f.autor}`;
  linea1 += " .";
  const pubBits = [];
  if (f.edicion) pubBits.push(f.edicion);
  const lugarEditorial = [f.lugar, f.editorial].filter(Boolean).join(" : ");
  if (lugarEditorial || f.anio) pubBits.push([lugarEditorial, f.anio].filter(Boolean).join(", "));
  if (pubBits.length) linea1 += " — " + pubBits.join(". — ") + ".";
  partes.push(linea1);

  const fisicaBits = [];
  if (f.descripcion_fisica) fisicaBits.push(f.descripcion_fisica);
  if (f.serie) fisicaBits.push(`(${f.serie})`);
  if (fisicaBits.length) partes.push(fisicaBits.join(" — "));

  (f.notas || []).forEach(n => partes.push(n));

  return partes.join("<br>");
}

function renderFicha(f) {
  const materias = (f.materias || []).map((m, i) => `${i + 1}. ${m}.`).join(" ");

  const sucursalesFilas = (f.ejemplares || [])
    .map(ej => `<tr><td>${ej.biblioteca ?? ""}</td><td>${ej.seccion ?? ""}</td><td>${ej.signatura ?? t("sin_sig")}</td><td>${ej.codigo_barras ?? ""}</td></tr>`)
    .join("");

  return `
    <div class="ficha-panel" data-ficha-panel="isbd">
      <div class="isbd-card">
        ${f.cdu ? `<div class="isbd-signatura">${f.cdu}</div>` : ""}
        ${f.autor ? `<div class="isbd-autor">${f.autor}</div>` : ""}
        <div class="isbd-parrafo">${renderIsbdParrafo(f)}</div>
        ${materias ? `<div class="isbd-materias">${materias}</div>` : ""}
        ${f.isbn ? `<div class="isbd-isbn">ISBN ${f.isbn}</div>` : ""}
        <p class="isbd-nota-sistema">${t("ficha_nota_sistema")}</p>
      </div>
    </div>
    <div class="ficha-panel" data-ficha-panel="sucursales" hidden>
      ${
        sucursalesFilas
          ? `<div class="table-wrap"><table class="ledger-table sucursales-table">
               <thead><tr><th>${t("ficha_col_biblioteca")}</th><th>${t("ficha_col_seccion")}</th><th>${t("ficha_col_signatura")}</th><th>${t("ficha_col_codigo_barras")}</th></tr></thead>
               <tbody>${sucursalesFilas}</tbody>
             </table></div>`
          : `<p class="hint">${t("ficha_sin_ejemplares")}</p>`
      }
    </div>
  `;
}

$("#ficha-close").addEventListener("click", () => { $("#ficha-overlay").hidden = true; });
$("#ficha-overlay").addEventListener("click", e => {
  if (e.target.id === "ficha-overlay") $("#ficha-overlay").hidden = true;
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("#ficha-overlay").hidden) $("#ficha-overlay").hidden = true;
});

// ---------- paleta de gráficos: coherente con la estética "fichero de biblioteca" ----------
const CHART_COLORS = {
  verde: "#2F5233",
  oro: "#B08D3E",
  rojo: "#A23B2E",
  azulPetroleo: "#3E6B72",
  marronCuero: "#8C6238",
  ciruela: "#6B4F6B",
};

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
      maintainAspectRatio: false,
      plugins: { legend: { display: type === "doughnut" } },
      font: { family: "Public Sans" },
      ...extraOptions,
    },
  });
}

// ---------- arranque ----------
(async function init() {
  applyStaticTranslations();
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
