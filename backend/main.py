"""
Gestión de la Colección — Backend API
======================================
Reimplementación en FastAPI de la lógica original de app.py (Streamlit),
separando por completo el procesamiento de datos de la interfaz.

Endpoints:
  GET  /api/bibliotecas
  POST /api/analizar
  GET  /api/analisis/general
  GET  /api/analisis/cdu
  GET  /api/analisis/signatura/opciones
  GET  /api/analisis/signatura
  GET  /api/recomendaciones/generales
  GET  /api/recomendaciones/cdu
  GET  /api/ficha/{id_sistema}
  GET  /api/estado
"""

import os
import re
import sqlite3
import threading
import time
import urllib.request
import uuid
from io import BytesIO
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymarc.marcxml import parse_xml_to_array
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================
# CONFIGURACIÓN
# ==========================================
DB_PATH = os.environ.get("DB_PATH", "gestion_coleccion.db")
DB_URL = os.environ.get(
    "DB_URL",
    "https://www.dropbox.com/scl/fi/xpmxz61of4ohqjuzju7e3/bibliotecas_navarra2_filtrado.db?rlkey=dyiscet4s4wts02ffmffj9n6g&st=jlto2dmf&dl=1",
)
SESSION_TTL_SECONDS = 3 * 60 * 60  # 3 horas
ANIO_ACTUAL = 2026

BIBLIOTECAS = {
    "Ablitas": 2610, "Aibar / Oibar": 769, "Allo": 988, "Altsasu / Alsasua": 7590, "Andosilla": 2882,
    "Ansoáin / Antsoain": 10608, "Añorbe": 628, "Aoiz, Agoitz": 2970, "Aranguren": 12517, "Arbizu": 1126,
    "Arguedas": 2313, "Arroniz": 1035, "Artajona": 1772, "Artica / Artika": 4848, "Aurizberri / Espinal": 2627,
    "Ayegui, Aiegi": 2531, "Azagra": 3749, "Barañain": 19575, "Baztan": 7831, "Bera": 3792, "Beriáin": 4129,
    "Berriozar": 10919, "Bibliobús": 8700, "Buñuel": 2309, "Burlada / Burlata": 20865, "Cabanillas": 1379,
    "Cadreita": 2186, "Caparroso": 2786, "Cárcar": 1150, "Carcastillo": 2435, "Cascante": 4050, "Cáseda": 969,
    "Castejón": 4435, "Cintruénigo": 8265, "Cirauqui / Zirauki": 467, "Corella": 8629, "Cortes": 3149,
    "Doneztebe / Santesteban": 1858, "Valle de Egües / Egusibar": 22121, "Estella / Lizarra": 14195,
    "Etxarri Aranatz": 2521, "Falces": 2375, "Fitero": 2146, "Fontellas": 1005, "Funes": 2542, "Fustiñana": 2457,
    "Huarte / Uharte": 7562, "Irurtzun": 2316, "Larraga": 2087, "Leitza": 3016, "Lekunberri": 1689,
    "Lerín": 1789, "Lesaka": 2731, "Lodosa": 4894, "Los Arcos": 1151, "Lumbier": 1326, "Mañeru": 445,
    "Marcilla": 2875, "Mélida": 715, "Mendavia": 3496, "Mendigorria": 1191, "Milagro": 3549,
    "Miranda de Arga": 917, "Monteagudo": 1102, "Murchante": 4237, "Noain": 8429, "Obanos": 920,
    "Olazti / Olaztigutía": 1483, "Olite / Erriberri": 4019, "Orkoien": 4051, "Oteiza": 923,
    "Peralta / Azkoien": 5979, "PNA - Biblioteca de Navarra": 208243, "PNA - Civican": 19418,
    "PNA - Echavacoiz": 5447, "PNA - Iturrama": 22354, "PNA - Mendillorri": 18747, "PNA - Milagrosa": 34998,
    "PNA - San Francisco": 25864, "PNA - San Jorge": 22203, "PNA - San Pedro": 26896, "PNA - Txantrea": 20264,
    "PNA - Yamaguchi": 16372, "Puente la Reina / Gares": 2944, "Ribaforada": 3715, "Roncal / Erronkari": 209,
    "San Adrián": 6429, "Sangüesa / Zangoza": 4814, "Sartaguda": 1328, "Sesma": 1226, "Tafalla": 10698,
    "Tudela": 37791, "Ultzama": 1636, "Urdiain": 638, "Valtierra": 2423, "Viana": 4370, "Villafranca": 3004,
    "Villava / Atarrabia": 10067, "Ziorda": 352, "Zizur Mayor / Zizur Nagusia": 15715,
}

app = FastAPI(title="Gestión de la Colección API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# ESTADO GLOBAL: CONEXIÓN SQLITE (RED DE BIBLIOTECAS)
# ==========================================
_db_lock = threading.Lock()
_db_conn: Optional[sqlite3.Connection] = None
_db_status = {"ready": False, "error": None, "downloading": False}


def _preparar_base_de_datos():
    global _db_conn
    with _db_lock:
        if _db_status["ready"] or _db_status["downloading"]:
            return
        _db_status["downloading"] = True
    try:
        descargar = False
        if not os.path.exists(DB_PATH):
            descargar = True
        elif os.path.getsize(DB_PATH) < 10_000:
            os.remove(DB_PATH)
            descargar = True
        if descargar:
            urllib.request.urlretrieve(DB_URL, DB_PATH)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.create_function(
            "REGEXP", 2,
            lambda expr, item: bool(re.search(expr, str(item), re.IGNORECASE)) if item else False,
        )
        # Índices para que los JOIN/GROUP BY de recomendaciones (que operan sobre
        # el catálogo completo de la red) no acaben haciendo un full table scan
        # en cada petición. CREATE INDEX IF NOT EXISTS es barato si ya existen.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ejemplares_id_sistema ON ejemplares(id_sistema)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ejemplares_biblioteca ON ejemplares(biblioteca)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_libros_id_sistema ON libros(id_sistema)")
        conn.commit()
        global _db_conn
        _db_conn = conn
        _db_status["ready"] = True
    except Exception as e:  # noqa: BLE001
        _db_status["error"] = str(e)
    finally:
        _db_status["downloading"] = False


@app.on_event("startup")
def _startup():
    threading.Thread(target=_preparar_base_de_datos, daemon=True).start()


def get_conn() -> sqlite3.Connection:
    if not _db_status["ready"] or _db_conn is None:
        detail = _db_status["error"] or "La base de datos de la red todavía se está preparando. Vuelve a intentarlo en un minuto."
        raise HTTPException(status_code=503, detail=detail)
    return _db_conn


# ==========================================
# ESTADO EN MEMORIA: SESIONES DE ANÁLISIS SUBIDO POR EL USUARIO
# ==========================================
SESSIONS: dict[str, dict] = {}


def _limpiar_sesiones_caducadas():
    ahora = time.time()
    caducadas = [sid for sid, s in SESSIONS.items() if ahora - s["ts"] > SESSION_TTL_SECONDS]
    for sid in caducadas:
        SESSIONS.pop(sid, None)


def get_session(session_id: str) -> dict:
    _limpiar_sesiones_caducadas()
    s = SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o caducada. Vuelve a subir los archivos.")
    return s


# ==========================================
# PROCESAMIENTO DE FICHEROS SUBIDOS (idéntico a la lógica original)
# ==========================================
def procesar_datos(topo_bytes, nunca_bytes, mas2_bytes, catalogo_bytes, tipo_analisis, num_caracteres):
    if not topo_bytes or not catalogo_bytes:
        return None, 0

    topo_text = topo_bytes.decode("utf-8", errors="replace")
    data = []
    for line in topo_text.split("\n"):
        line = line.strip()
        if not line or re.search(r"^(\d{2}/\d{2}/\d{4}|LISTADO|Signatura|-----)", line):
            continue
        match = re.search(r"\b(\d{7,})\b", line)
        if not match:
            continue
        record_id = int(match.group(1))
        sign_match = re.search(r"(.+?)\s+84\s+[A-Z]{2}", line)
        signatura = sign_match.group(1).strip() if sign_match else line
        title_match = re.search(r"\d{7,}\s+(.{10,})", line)
        title = title_match.group(1).strip() if title_match else "Título no detectado"
        data.append({"record_id": record_id, "signatura_real": signatura, "titulo": title})

    df_topo = pd.DataFrame(data).drop_duplicates(subset=["record_id"])
    if df_topo.empty:
        return None, 0

    cat_text = catalogo_bytes.decode("utf-8", errors="replace")
    cat_text = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "", cat_text)
    year_dict = {}
    matches = list(re.finditer(r"\b\d{7,}\b", cat_text))
    for i, m in enumerate(matches):
        rid = int(m.group())
        start = m.start()
        end = matches[i + 1].start() if i < len(matches) - 1 else len(cat_text)
        block = cat_text[start:end]
        years = re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", block)
        years = [int(y) for y in years if 1800 <= int(y) <= ANIO_ACTUAL]
        if years:
            year_dict[rid] = max(years)

    df_final = df_topo[df_topo["record_id"].isin(year_dict.keys())].copy()
    df_final["year"] = df_final["record_id"].map(year_dict)
    df_final["prestamos"] = 1

    if nunca_bytes:
        nunca_text = nunca_bytes.decode("utf-8", errors="replace")
        nunca_ids = {int(x) for x in re.findall(r"\b\d{7,}\b", nunca_text)}
        df_final.loc[df_final["record_id"].isin(nunca_ids), "prestamos"] = 0

    if mas2_bytes:
        mas2_text = mas2_bytes.decode("utf-8", errors="replace")
        mas2_ids = {int(x) for x in re.findall(r"\b\d{7,}\b", mas2_text)}
        df_final.loc[df_final["record_id"].isin(mas2_ids), "prestamos"] = 2

    df_final["prestado"] = df_final["prestamos"] > 0

    def clasificar_dinamico(sign):
        if not sign or not isinstance(sign, str):
            return "Sin clasificar"
        s = sign.strip().upper()
        if tipo_analisis == "Clasificación Mixta Estándar (CDU + Letras)":
            if re.search(r"\bI\s+DVD\b", s):
                return "I DVD (DVD Infantil)"
            if re.search(r"\bDVD\b", s):
                return "DVD Audiovisual"
            if re.search(r"^IC\b", s):
                return "IC (Comic Infantil)"
            if re.search(r"^C\b", s):
                return "C (Comic Adultos)"
            if re.search(r"\bIP\b", s):
                return "IP (Infantil Poesía)"
            if re.search(r"\bIT\b", s):
                return "IT (Infantil Teatro)"
            if re.search(r"^I\s+[12356789]", s):
                return "CDU Infantil"
            match_inf = re.match(r"^(I[0-3])", s)
            if match_inf:
                return f"{match_inf.group(1)} (Infantil)"
            if re.search(r"\bJN\b", s):
                return "JN (Juvenil)"
            if re.search(r"\bN\s", s):
                return "Ficción / Narrativa"
            if re.search(r"\bP\s", s):
                return "Poesía"
            if re.search(r"\bT\s", s):
                return "Teatro"
            m = re.match(r"^(\d)", s)
            if m:
                cats = {
                    "0": "0 - Generalidades", "1": "1 - Filosofía", "2": "2 - Religión",
                    "3": "3 - Ciencias Sociales", "4": "4 - Lingüística",
                    "5": "5 - Ciencias Puras", "6": "6 - Tecnología",
                    "7": "7 - Arte / Deportes", "8": "8 - Literatura",
                    "9": "9 - Historia / Geografía",
                }
                return cats.get(m.group(1), f"CDU {m.group(1)}xx")
            return "Otros"
        elif tipo_analisis == "Solo Dígitos Iniciales de la CDU":
            m = re.match(r"^(\d+)", s)
            return f"CDU {m.group(1)[0]}" if m else "Ficción / Otros"
        elif tipo_analisis == "Longitud Fija (Primeros caracteres)":
            return s[:num_caracteres]
        return "Otros"

    df_final["categoria"] = df_final["signatura_real"].apply(clasificar_dinamico)
    return df_final, (len(df_topo) - len(df_final))


def _clasificar_macro(cat: str) -> str:
    c = str(cat).strip().upper()
    if "DVD" in c or "AUDIOVISUAL" in c or "CD" in c:
        return "Audiovisuales"
    if re.match(r"^(I|JN|IC|IP|IT|INFANTIL|JUVENIL)(\s|\d+|-|$)", c):
        return "Infantil/Juvenil"
    return "Adultos"


def _es_categoria_infantil(categoria) -> bool:
    cat_str = str(categoria).upper()
    if "INFANTIL" in cat_str or "JUVENIL" in cat_str:
        return True
    if re.match(r"^(I[0-9]?|JN|IC|IP|IT)(\s|$)", cat_str):
        return True
    return False


def _extraer_raiz(sig) -> str:
    s = str(sig).strip().upper()
    m = re.match(r"^([A-Z]*\s*\d{2})", s)
    if m:
        return m.group(1)
    return s.split()[0][:3] if s.split() else s


def _wildcard_mask(series: pd.Series, patron: str) -> pd.Series:
    """Replica el filtrado con comodines '*' del original, o 'empieza por' si no hay '*'."""
    serie_norm = series.astype(str).str.upper().str.strip()
    if "*" in patron:
        regex_patron = re.escape(patron).replace(r"\*", ".*")
        return serie_norm.str.match(regex_patron, na=False)
    return serie_norm.str.startswith(patron, na=False)


# ==========================================
# ENDPOINTS
# ==========================================
@app.get("/api/estado")
def estado():
    return {"db_lista": _db_status["ready"], "db_error": _db_status["error"], "descargando": _db_status["downloading"]}


@app.get("/api/bibliotecas")
def bibliotecas():
    return dict(sorted(BIBLIOTECAS.items()))


@app.post("/api/analizar")
async def analizar(
    biblioteca: str = Form(...),
    tipo_analisis: str = Form("Clasificación Mixta Estándar (CDU + Letras)"),
    num_caracteres: int = Form(3),
    topo: UploadFile = File(...),
    catalogo: UploadFile = File(...),
    nunca: Optional[UploadFile] = File(None),
    mas2: Optional[UploadFile] = File(None),
):
    if biblioteca not in BIBLIOTECAS:
        raise HTTPException(status_code=400, detail="Biblioteca no reconocida.")

    topo_bytes = await topo.read()
    catalogo_bytes = await catalogo.read()
    nunca_bytes = await nunca.read() if nunca else None
    mas2_bytes = await mas2.read() if mas2 else None

    df, huerfanos = procesar_datos(topo_bytes, nunca_bytes, mas2_bytes, catalogo_bytes, tipo_analisis, num_caracteres)
    if df is None or df.empty:
        raise HTTPException(status_code=422, detail="No se pudieron extraer registros válidos de los archivos subidos.")

    df["macro_seccion"] = df["categoria"].apply(_clasificar_macro)
    df["es_infantil"] = df["categoria"].apply(_es_categoria_infantil)

    poblacion = BIBLIOTECAS[biblioteca]
    total_docs = len(df)
    pct_prestados = float(df["prestado"].sum() / total_docs * 100) if total_docs else 0.0
    edad_media = df["year"].mean()
    docs_por_habitante = total_docs / poblacion if poblacion else 0.0

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "df": df, "huerfanos": huerfanos, "biblioteca": biblioteca,
        "poblacion": poblacion, "ts": time.time(),
    }

    return {
        "session_id": session_id,
        "biblioteca": biblioteca,
        "poblacion": poblacion,
        "huerfanos": huerfanos,
        "kpis": {
            "total_docs": total_docs,
            "pct_prestados": round(pct_prestados, 1),
            "edad_media": None if np.isnan(edad_media) else int(edad_media),
            "docs_por_habitante": round(docs_por_habitante, 2),
        },
    }


@app.get("/api/analisis/general")
def analisis_general(session_id: str):
    s = get_session(session_id)
    df = s["df"]
    poblacion = s["poblacion"]
    total_docs = len(df)
    docs_por_habitante = total_docs / poblacion if poblacion else 0.0

    if poblacion <= 5000:
        pauta_hab, pauta_min, pauta_max = 2.5, 4000, 5500
    elif poblacion <= 10000:
        pauta_hab, pauta_min, pauta_max = 2.5, 7000, 12500
    elif poblacion <= 20000:
        pauta_hab, pauta_min, pauta_max = 2.0, 12500, 20000
    elif poblacion <= 50000:
        pauta_hab, pauta_min, pauta_max = 2.0, 20000, 65000
    elif poblacion <= 100000:
        pauta_hab, pauta_min, pauta_max = 1.5, 45000, 80000
    else:
        pauta_hab, pauta_min, pauta_max = 1.5, 80000, 95000

    if total_docs < 2500:
        diag_vol = {"nivel": "error", "texto": f"Alerta: suelo mínimo absoluto IFLA es de 2.500 obras. Tienes {total_docs:,}."}
    elif total_docs < pauta_min:
        diag_vol = {"nivel": "warning", "texto": f"Déficit de fondo: recomendado {pauta_min:,}-{pauta_max:,}. Tienes {total_docs:,}."}
    elif total_docs > pauta_max:
        diag_vol = {"nivel": "info", "texto": f"Fondo extenso: el rango inicial recomendado es {pauta_min:,}-{pauta_max:,}. Tienes {total_docs:,}."}
    else:
        diag_vol = {"nivel": "success", "texto": f"Óptimo: volumen adecuado dentro del rango ({pauta_min:,}-{pauta_max:,})."}

    if docs_por_habitante > 3.5:
        diag_hab = {"nivel": "warning", "texto": f"Colección demasiado grande: {docs_por_habitante:.2f} libros/persona (óptimo {pauta_hab}, máx. sugerido 3.5)."}
    elif docs_por_habitante < pauta_hab:
        diag_hab = {"nivel": "warning", "texto": f"Ratio bajo: {docs_por_habitante:.2f} doc/hab. (mínimo recomendado {pauta_hab})."}
    else:
        diag_hab = {"nivel": "success", "texto": f"Ratio óptimo: {docs_por_habitante:.2f} doc/hab."}

    macro_counts = df["macro_seccion"].value_counts()
    tabla_macro = [
        {"seccion": nombre, "pct": round(float(macro_counts.get(nombre, 0)) / total_docs * 100, 1) if total_docs else 0.0}
        for nombre in ["Adultos", "Infantil/Juvenil", "Audiovisuales"]
    ]

    status_map = {0: "Nunca prestado", 1: "Prestado", 2: "Muy prestado"}
    status_counts = df["prestamos"].map(status_map).value_counts()
    rotacion = [{"estado": k, "cantidad": int(v)} for k, v in status_counts.items()]

    years = df["year"].dropna()
    hist = {"labels": [], "counts": []}
    if not years.empty:
        counts, edges = np.histogram(years, bins=25)
        hist["labels"] = [int((edges[i] + edges[i + 1]) / 2) for i in range(len(counts))]
        hist["counts"] = [int(c) for c in counts]

    return {
        "diagnostico_volumen": diag_vol,
        "diagnostico_ratio": diag_hab,
        "distribucion_macro": tabla_macro,
        "rotacion": rotacion,
        "cronologia": hist,
    }


@app.get("/api/analisis/cdu")
def analisis_cdu(session_id: str):
    s = get_session(session_id)
    df = s["df"]

    df_metrics = df.groupby("categoria").agg(
        volumenes=("record_id", "count"),
        prestados=("prestado", "sum"),
        anio_medio=("year", "mean"),
    ).reset_index()
    df_metrics["pct_uso"] = (df_metrics["prestados"] / df_metrics["volumenes"] * 100).round(1)
    df_metrics["anio_medio"] = df_metrics["anio_medio"].fillna(0).astype(int)
    df_metrics["es_infantil"] = df_metrics["categoria"].apply(_es_categoria_infantil)

    def _serializar(sub):
        sub = sub.sort_values(by="volumenes", ascending=False)
        return [
            {"categoria": r.categoria, "volumenes": int(r.volumenes), "pct_uso": float(r.pct_uso), "anio_medio": int(r.anio_medio)}
            for r in sub.itertuples()
        ]

    return {
        "adultos": _serializar(df_metrics[~df_metrics["es_infantil"]]),
        "infantil": _serializar(df_metrics[df_metrics["es_infantil"]]),
    }


@app.get("/api/analisis/signatura/opciones")
def signatura_opciones(session_id: str, seccion: str = "todo", categoria: Optional[str] = None):
    s = get_session(session_id)
    df = s["df"]
    if seccion == "adultos":
        df = df[~df["es_infantil"]]
    elif seccion == "infantil":
        df = df[df["es_infantil"]]

    categorias = sorted(df["categoria"].dropna().unique().tolist())

    subopciones = []
    if categoria and categoria != "Todas":
        df_cat = df[df["categoria"] == categoria]
        raices = df_cat["signatura_real"].dropna().apply(_extraer_raiz).unique()
        subopciones = sorted(raices.tolist())

    return {"categorias": categorias, "subsignaturas": subopciones}


@app.get("/api/analisis/signatura")
def signatura(
    session_id: str,
    seccion: str = "todo",
    busqueda: str = "",
    categoria: str = "Todas",
    sub: str = "Todas",
    prestamo: str = "todos",
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    s = get_session(session_id)
    df = s["df"]

    if seccion == "adultos":
        df = df[~df["es_infantil"]]
    elif seccion == "infantil":
        df = df[df["es_infantil"]]

    busqueda = busqueda.strip().upper()
    if busqueda:
        df = df[_wildcard_mask(df["signatura_real"], busqueda)]

    if categoria != "Todas":
        df = df[df["categoria"] == categoria]

    if sub != "Todas":
        df = df[df["signatura_real"].str.upper().str.startswith(sub, na=False)]

    if prestamo == "nunca":
        df = df[df["prestamos"] == 0]
    elif prestamo == "estandar":
        df = df[df["prestamos"] == 1]
    elif prestamo == "alta":
        df = df[df["prestamos"] == 2]

    total = len(df)
    pct_prestados = round(float((df["prestamos"] > 0).sum()) / total * 100, 1) if total else 0.0
    anios_validos = df["year"].dropna()
    anio_medio = int(anios_validos.mean()) if not anios_validos.empty else None

    start = (page - 1) * page_size
    pagina = df.iloc[start:start + page_size]
    filas = [
        {
            "id_sistema": int(r.record_id),
            "signatura": r.signatura_real,
            "titulo": r.titulo,
            "anio": None if pd.isna(r.year) else int(r.year),
            "categoria": r.categoria,
            "prestamos": int(r.prestamos),
        }
        for r in pagina.itertuples()
    ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "filas": filas,
        "resumen": {"num_volumenes": total, "pct_prestados": pct_prestados, "anio_medio": anio_medio},
    }


# ---------- Recomendaciones (usan la BD de la red completa) ----------

def obtener_recomendaciones_automaticas(conexion, biblioteca, limite=50):
    # NOT EXISTS con subconsulta correlacionada suele optimizar mucho mejor en SQLite
    # que NOT IN con un subselect independiente, sobre todo con un índice en
    # ejemplares(id_sistema, biblioteca). Con NOT IN, SQLite normalmente materializa
    # toda la subconsulta y compara fila a fila, algo muy costoso si ejemplares
    # contiene el catálogo completo de la red.
    query = """
        SELECT l.id_sistema, l.titulo, l.autor, l.anio, COUNT(DISTINCT e.biblioteca) as total_bibliotecas
        FROM libros l
        JOIN ejemplares e ON l.id_sistema = e.id_sistema
        WHERE NOT EXISTS (
            SELECT 1 FROM ejemplares e2
            WHERE e2.id_sistema = l.id_sistema AND TRIM(UPPER(e2.biblioteca)) = ?
        )
        GROUP BY l.id_sistema, l.titulo, l.autor, l.anio
        ORDER BY total_bibliotecas DESC
        LIMIT ?
    """
    params = [biblioteca.upper().strip(), int(limite)]
    return pd.read_sql_query(query, conexion, params=params)


@app.get("/api/recomendaciones/generales")
def recomendaciones_generales(biblioteca: str, limite: int = 50):
    if biblioteca not in BIBLIOTECAS:
        raise HTTPException(status_code=400, detail="Biblioteca no reconocida.")
    conn = get_conn()
    df = obtener_recomendaciones_automaticas(conn, biblioteca, limite)
    if df.empty:
        return {"resultados": []}
    return {
        "resultados": [
            {"id_sistema": int(r.id_sistema), "titulo": r.titulo, "autor": r.autor, "anio": r.anio, "num_bibliotecas": int(r.total_bibliotecas)}
            for r in df.itertuples()
        ]
    }


MENUS_ADULTOS = {
    "Ficción": "Ficción Adultos (821)", "CDU 0": "CDU 0 · Generalidades", "CDU 1": "CDU 1 · Filosofía / Psicología",
    "CDU 2": "CDU 2 · Religión / Teología", "CDU 3": "CDU 3 · Ciencias Sociales / Economía",
    "CDU 5": "CDU 5 · Ciencias Puras / Naturales", "CDU 6": "CDU 6 · Ciencias Aplicadas / Tecnología",
    "CDU 7": "CDU 7 · Bellas Artes / Deportes", "CDU 8": "CDU 8 · Lingüística / Literatura",
    "CDU 9": "CDU 9 · Geografía / Historia",
}
MENUS_INFANTIL = {
    "I0": "I0 · Bebeteca", "I1": "I1 · Hasta 6 años", "I2": "I2 · 7 a 9 años",
    "I3": "I3 · 10 a 12 años", "JN": "JN · Juvenil",
    "I CDU 0": "I CDU 0 · Generalidades", "I CDU 1": "I CDU 1 · Filosofía", "I CDU 2": "I CDU 2 · Religión",
    "I CDU 3": "I CDU 3 · Ciencias Sociales", "I CDU 4": "I CDU 4 · Lengua", "I CDU 5": "I CDU 5 · Ciencias Puras",
    "I CDU 6": "I CDU 6 · Ciencias Aplicadas", "I CDU 7": "I CDU 7 · Arte / Deportes",
    "I CDU 8": "I CDU 8 · Literatura", "I CDU 9": "I CDU 9 · Geografía e Historia",
}


def _clasificar_infantil(todas_sigs):
    if not todas_sigs:
        return None
    sigs = [x.strip().upper() for x in str(todas_sigs).split("||") if x.strip()]
    for sig in sigs:
        m = re.search(r"\b(I0|I1|I2|I3|JN)\b", sig)
        if m:
            return m.group(1)
        m2 = re.search(r"\bI\s+([0-9])\b", sig)
        if m2:
            return f"I CDU {m2.group(1)}"
        m3 = re.search(r"\bI([4-9])\b", sig)
        if m3:
            return f"I CDU {m3.group(1)}"
    return None


def _clasificar_libro_cdu(cdu: str, todas_signaturas: str):
    cdu = str(cdu).strip().upper()
    if cdu.startswith("087.5"):
        cat_inf = _clasificar_infantil(todas_signaturas)
        if cat_inf:
            return "Infantil", cat_inf
        return None, None
    if cdu.startswith("821"):
        return "Adultos", "Ficción"
    m = re.match(r"^(\d)", cdu)
    if m and m.group(1) in ["0", "1", "2", "3", "5", "6", "7", "8", "9"]:
        return "Adultos", f"CDU {m.group(1)}"
    return None, None


@app.get("/api/recomendaciones/cdu")
def recomendaciones_cdu(biblioteca: str, limite_cdu: int = 10, anio_minimo: int = 2015, busqueda_cdu: str = ""):
    if biblioteca not in BIBLIOTECAS:
        raise HTTPException(status_code=400, detail="Biblioteca no reconocida.")
    conn = get_conn()

    query_cdu = """
        SELECT l.id_sistema, l.titulo, l.autor, l.anio, l.cdu,
               COUNT(DISTINCT e.biblioteca) AS id_red_bibliotecas,
               GROUP_CONCAT(e.signatura, '||') AS todas_signaturas
        FROM libros l
        JOIN ejemplares e ON l.id_sistema = e.id_sistema
        WHERE l.id_sistema NOT IN (
            SELECT DISTINCT id_sistema FROM ejemplares WHERE UPPER(TRIM(biblioteca)) = ?
        )
        AND CAST(COALESCE(l.anio, 0) AS INTEGER) >= ?
        GROUP BY l.id_sistema, l.titulo, l.autor, l.anio, l.cdu
        HAVING id_red_bibliotecas > 0
    """
    df = pd.read_sql_query(query_cdu, conn, params=[biblioteca.upper().strip(), int(anio_minimo)])
    if df.empty:
        return {"adultos": {}, "infantil": {}}

    busqueda_cdu = busqueda_cdu.strip().upper()
    if busqueda_cdu:
        df = df[_wildcard_mask(df["cdu"], busqueda_cdu)]
    if df.empty:
        return {"adultos": {}, "infantil": {}}

    clasif = df.apply(lambda r: _clasificar_libro_cdu(r["cdu"], r.get("todas_signaturas", "")), axis=1)
    df["subtab"] = [c[0] for c in clasif]
    df["categoria_final"] = [c[1] for c in clasif]
    df = df[df["subtab"].notna()].sort_values("id_red_bibliotecas", ascending=False)

    def _agrupar(subtab, menus):
        salida = {}
        for clave, titulo in menus.items():
            g = df[(df["subtab"] == subtab) & (df["categoria_final"] == clave)].head(limite_cdu)
            if not g.empty:
                salida[clave] = {
                    "titulo": titulo,
                    "items": [
                        {
                            "id_sistema": r.id_sistema,
                            "titulo": r.titulo,
                            "autor": r.autor,
                            "anio": r.anio,
                            "cdu": r.cdu,
                            "num_bibliotecas": int(r.id_red_bibliotecas),
                        }
                        for r in g.itertuples()
                    ],
                }
        return salida

    return {
        "adultos": _agrupar("Adultos", MENUS_ADULTOS),
        "infantil": _agrupar("Infantil", MENUS_INFANTIL),
    }


# ==========================================
# FICHA CATALOGRÁFICA (registro MARC completo)
# ==========================================
CAMPOS_FICHA = {
    "250": "Edición",
    "300": "Descripción física",
    "490": "Serie",
    "500": "Notas",
    "505": "Contenido",
    "520": "Resumen",
}


@app.get("/api/ficha/{id_sistema}")
def ficha_catalografica(id_sistema: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT marcxml FROM marc_completo WHERE id_sistema = ?", (id_sistema,)
        ).fetchone()
    except sqlite3.OperationalError:
        raise HTTPException(
            status_code=501,
            detail="Esta base de datos no incluye fichas catalográficas (falta la tabla marc_completo).",
        )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No hay ficha MARC disponible para este registro (puede ser anterior al corte por año de la base de datos).",
        )

    xml_envuelto = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<collection xmlns="http://www.loc.gov/MARC21/slim">'
        + row[0].encode("utf-8")
        + b"</collection>"
    )
    registros = parse_xml_to_array(BytesIO(xml_envuelto))
    if not registros:
        raise HTTPException(status_code=500, detail="No se pudo interpretar el registro MARC almacenado.")
    record = registros[0]

    campos_extra = {}
    for tag, etiqueta in CAMPOS_FICHA.items():
        valores = [str(c) for c in record.get_fields(tag)]
        if valores:
            campos_extra[etiqueta] = valores

    materias = [str(c) for c in record.get_fields("650")]

    ejemplares = conn.execute(
        "SELECT biblioteca, seccion, signatura, codigo_barras FROM ejemplares WHERE id_sistema = ?",
        (id_sistema,),
    ).fetchall()

    return {
        "id_sistema": id_sistema,
        "titulo": record.title,
        "autor": record.author,
        "isbn": record.isbn,
        "cdu": record["080"]["a"] if "080" in record and "a" in record["080"] else None,
        "editorial": record["260"]["b"] if "260" in record and "b" in record["260"] else None,
        "anio": record["260"]["c"] if "260" in record and "c" in record["260"] else None,
        "materias": materias,
        "campos": campos_extra,
        "ejemplares": [
            {"biblioteca": r[0], "seccion": r[1], "signatura": r[2], "codigo_barras": r[3]}
            for r in ejemplares
        ],
    }


# ==========================================
# SERVIR EL FRONTEND ESTÁTICO
# ==========================================
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "/app/frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
