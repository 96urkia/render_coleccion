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
import charset_normalizer
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
    "https://www.dropbox.com/scl/fi/fly8fwgkybzo3zua5kynp/bibliotecas_navarra3_filtrado.db?rlkey=zpxzy05o0906reyy29h0xt63c&st=jw1yhstj&dl=1",
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
_db_status = {"ready": False, "error": None, "downloading": False, "fts": False}


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

        # ¿Trae esta .db los índices FTS5 (trigram) de materias_fts/libros_fts?
        # Las bases generadas con el script antiguo (sin la migración FTS) no
        # los tienen: en ese caso se sigue usando el filtrado en Python como
        # respaldo, para no romper despliegues con una .db todavía sin migrar.
        tablas_fts = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('materias_fts', 'libros_fts')"
            ).fetchall()
        }
        _db_status["fts"] = {"materias_fts", "libros_fts"}.issubset(tablas_fts)

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
def _decodificar_bytes(data: bytes) -> str:
    """Decodifica los .txt exportados por AbsysNet.

    Estos ficheros vienen casi siempre en Windows-1252/Latin-1 (con acentos,
    "ñ", etc.), no en UTF-8, aunque a veces sí llegan en UTF-8 real.

    OJO con el enfoque "todo o nada": antes se probaba UTF-8 estricto y, si
    fallaba en CUALQUIER punto del fichero (aunque fuera un único byte suelto
    corrupto, p.ej. pegado por otro programa), se descartaba el fichero
    ENTERO y se re-decodificaba completo como cp1252. El problema es que si
    el fichero SÍ era mayormente UTF-8 válido, ese único byte roto hacía que
    también se mal-interpretaran como cp1252 las secuencias UTF-8 que
    estaban perfectamente bien (p.ej. "Í" = bytes 0xC3 0x8D en UTF-8 se leía
    como "Ã" + un byte sin carácter asignado en cp1252, mostrado como el
    símbolo de reemplazo "�") — el "MINER�A" que se ve en el análisis viene
    de ahí.

    Para no repetir ese error, medimos CUÁNTO del fichero deja de encajar en
    UTF-8: si es un porcentaje mínimo (un byte suelto corrupto en miles de
    caracteres válidos), se trata como UTF-8 real y solo se pierde ese byte
    puntual (irrecuperable de todos modos). Si el porcentaje es alto, es que
    el fichero directamente NO está en UTF-8 (el caso típico), y ahí se usa
    charset-normalizer para detectar la codificación real por estadística
    del contenido, en vez de asumir siempre cp1252 a ciegas.
    """
    if not data:
        return ""
    try:
        return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        pass

    texto_relajado = data.decode("utf-8", errors="replace")
    ratio_roto = texto_relajado.count("\ufffd") / max(len(texto_relajado), 1)

    if ratio_roto < 0.005:
        # Prácticamente todo era UTF-8 válido: unos pocos bytes sueltos
        # corruptos no justifican re-decodificar el fichero entero con otra
        # codificación (eso es lo que rompía también los caracteres buenos).
        texto = texto_relajado
    else:
        # El fichero no es UTF-8 de verdad. Se prueba cp1252 ESTRICTO (sin
        # errors="replace"): es la codificación habitual de estos exports
        # de AbsysNet, y si decodifica sin errores es la apuesta más fiable
        # (charset-normalizer, al ser puramente estadístico, a veces confunde
        # cp1252 con una codificación de otro idioma parecida, p.ej. cambiar
        # "año" por "ańo"). Solo si cp1252 estricto también falla (algún
        # byte de los pocos que cp1252 deja sin asignar) se recurre a
        # charset-normalizer, y en último caso a latin-1 (que no falla nunca).
        try:
            texto = data.decode("cp1252")
        except UnicodeDecodeError:
            mejor = charset_normalizer.from_bytes(data).best()
            texto = str(mejor) if mejor is not None else data.decode("latin-1")
    # AbsysNet exporta a veces con fin de línea Windows (\r\n). Varias regex
    # de más abajo anclan "^"/"$" a límite de línea (p.ej. para detectar el
    # nº de registro solo en su línea); si queda un "\r" colgando justo antes
    # del "\n", esas anclas no casan y el fichero entero deja de parsearse
    # bien. Normalizamos aquí una vez para no repetir el problema en cada regex.
    return texto.replace("\r\n", "\n").replace("\r", "\n")


# Encabezamiento de autor persona: "APELLIDOS, Nombre (fechas)". Si la línea
# no empieza así, se asume entrada por título (autor corporativo/anónimo).
_RE_AUTOR_PERSONA = re.compile(r"^[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ.\-\s]*,\s+\S")
_RE_NOTA_ISBN = re.compile(r"^(D\.?L\.?|ISBN)", re.IGNORECASE)


def _parsear_fichas_catalogo(cat_text: str) -> dict:
    """Extrae una ficha ISBD simplificada por registro a partir del fichero
    de 'Catálogo' (Formato 1 / Cuerpo 1 / Orden 8), que trae para cada libro
    el asiento bibliográfico completo (autor, título, edición, notas, ISBN,
    materias) en texto libre, no en columnas.

    No es un parseo MARC estricto (el fichero es texto de listado, no XML),
    así que se basa en heurísticas sobre la puntuación ISBD habitual. Para
    cada registro se recorta el bloque de texto entre su número de registro
    y la línea de "sucursal + signatura" que cierra la ficha (p.ej. "84 SL"),
    de modo que no se cuele el encabezado del siguiente registro.
    """
    # El listado va paginado: entre registros se cuelan saltos de página con
    # "Pág. N", la cabecera "Catálogo Topográfico" y la fecha de emisión.
    # Si no se limpian, acaban apareciendo en medio del párrafo ISBD.
    cat_text_limpio = re.sub(
        r"^\s*(Pág\.\s*\d+|Catálogo Topográfico.*|\d{2}/\d{2}/\d{4})\s*$",
        "", cat_text, flags=re.MULTILINE,
    )

    # El número de registro (código de barras) siempre aparece SOLO en su
    # propia línea, justo debajo de la signatura. No basta con \b\d{7,}\b:
    # un ISBN-13 sin guiones ("ISBN 9788491169031") también tiene 7+ dígitos
    # con límites de palabra y, si se usa esa regex laxa, se confunde con el
    # inicio de un registro nuevo, cortando la ficha real justo ahí y
    # perdiendo materias/autor de ese registro en adelante. Exigir que el
    # número esté solo en su línea evita ese falso corte.
    matches = list(re.finditer(r"^[ \t]*(\d{7,})[ \t]*$", cat_text_limpio, re.MULTILINE))
    fichas = {}
    for i, m in enumerate(matches):
        rid = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i < len(matches) - 1 else len(cat_text_limpio)
        bloque = cat_text_limpio[start:end]

        # La ficha de este registro termina en la línea "84 XX ..." (código
        # de sucursal de dos dígitos + sección de dos letras); lo que venga
        # después ya pertenece al encabezado del siguiente registro.
        cierre = re.search(r"^\s*\d{2}\s+[A-ZÁÉÍÓÚÑÜ]{2}\b.*$", bloque, re.MULTILINE)
        if cierre:
            bloque = bloque[: cierre.start()]

        lineas = [ln.strip() for ln in bloque.split("\n") if ln.strip()]
        if not lineas:
            continue

        autor = None
        resto = lineas
        if _RE_AUTOR_PERSONA.match(lineas[0]) and "/" not in lineas[0]:
            autor = lineas[0]
            resto = lineas[1:]
        if not resto:
            continue

        idx_isbn = next((i2 for i2, ln in enumerate(resto) if _RE_NOTA_ISBN.match(ln)), None)
        if idx_isbn is not None:
            titulo_lineas = resto[:idx_isbn]
            linea_isbn = resto[idx_isbn]
            materias_lineas = resto[idx_isbn + 1:]
        else:
            # Sin línea D.L./ISBN detectada: se asume que la última línea son
            # las materias (empiezan por "1.") y el resto es el título.
            if resto[-1].lstrip().startswith("1."):
                titulo_lineas, linea_isbn, materias_lineas = resto[:-1], "", [resto[-1]]
            else:
                titulo_lineas, linea_isbn, materias_lineas = resto, "", []

        titulo_par = re.sub(r"\s+", " ", " ".join(titulo_lineas)).strip()
        # La mención de responsabilidad empieza en " / autor"; a veces el
        # salto de línea original pegaba la barra al nombre ("...migratorias
        # \n/Scott Weidensaul"), así que solo exigimos espacio ANTES de la "/".
        partes_titulo = re.split(r"\s+/\s*", titulo_par, maxsplit=1)
        titulo = partes_titulo[0].strip(" .") or None
        resto_isbd = partes_titulo[1].strip() if len(partes_titulo) > 1 else None

        isbn_m = re.search(r"ISBN\s*([\dXx\-]{8,})", linea_isbn)
        isbn = isbn_m.group(1) if isbn_m else None

        materias_txt = re.sub(r"\s+", " ", " ".join(materias_lineas)).strip()
        # Corta la mención de asiento secundario en números romanos ("I.
        # Título", "II. Serie...", con o sin materias delante).
        corte = re.search(r"\b[IVXLC]+\.\s", materias_txt)
        if corte:
            materias_txt = materias_txt[: corte.start()]
        materias = [
            frag.strip(" .-")
            for frag in re.split(r"\d+\.\s*", materias_txt)
            if frag.strip(" .-")
        ]

        fichas[rid] = {
            "autor": autor,
            "titulo": titulo,
            "resto_isbd": resto_isbd,
            "isbn": isbn,
            "materias": materias,
        }
    return fichas


def _parsear_linea_topo(line: str):
    """Divide una línea del listado (topográfico / más prestados / no
    prestados) por las columnas de ancho fijo que usa AbsysNet:

        Signatura                  Sig. supl.   Suc.  Loc.   Cod. Bar.  Nº Reg.   Título
        0                          27           40    46     53         64        74

    Antes se usaba una regex "(.+?)\\s+84\\s+[A-Z]{2}" para cortar la
    signatura, pero esa regex no distingue dónde acaba la columna
    "Signatura" y empieza "Sig. supl." (p.ej. género "Histórica",
    "Policíaca"): se comía las dos como si fueran una sola, y ese texto de
    género acababa filtrándose en búsquedas de materia por error. Cortar
    por posición fija, tal cual vienen alineadas las columnas en el
    listado, evita esa mezcla. IMPORTANTE: no hacer .strip() a la línea
    completa antes de esto o se pierde la alineación de columnas.
    """
    def col(a, b=None):
        return (line[a:b] if b is not None else line[a:]).strip()

    return {
        "signatura": col(0, 27),
        "sig_supl": col(27, 40),
        "cod_bar": col(53, 64),
        "nreg": col(64, 74),
        "titulo": col(74),
    }


def procesar_datos(topo_bytes, nunca_bytes, mas2_bytes, catalogo_bytes, tipo_analisis, num_caracteres):
    if not topo_bytes or not catalogo_bytes:
        return None, 0, {}

    topo_text = _decodificar_bytes(topo_bytes)
    data = []
    for line in topo_text.split("\n"):
        line_sin_salto = line.rstrip("\n")
        cabecera = line_sin_salto.strip()
        if not cabecera or re.search(r"^(\d{2}/\d{2}/\d{4}|LISTADO|Signatura|-----)", cabecera):
            continue
        campos = _parsear_linea_topo(line_sin_salto)
        cod_bar = campos["cod_bar"]
        if not re.fullmatch(r"\d{6,}", cod_bar):
            # Línea sin código de barras reconocible (p.ej. fila rota o de
            # continuación): se ignora, igual que hacía la versión anterior
            # cuando no encontraba ningún grupo de 7+ dígitos.
            continue
        record_id = int(cod_bar)
        signatura = campos["signatura"]
        titulo = campos["titulo"].rstrip(" /") or "Título no detectado"
        data.append({
            "record_id": record_id,
            "signatura_real": signatura,
            "sig_supl": campos["sig_supl"],
            "titulo": titulo,
        })

    df_topo = pd.DataFrame(data).drop_duplicates(subset=["record_id"])
    if df_topo.empty:
        return None, 0, {}

    cat_text = _decodificar_bytes(catalogo_bytes)
    cat_text_sin_fechas = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "", cat_text)
    year_dict = {}
    # Mismo criterio que en _parsear_fichas_catalogo: el nº de registro va
    # solo en su línea, para no confundirlo con un ISBN-13 sin guiones.
    matches = list(re.finditer(r"^[ \t]*(\d{7,})[ \t]*$", cat_text_sin_fechas, re.MULTILINE))
    for i, m in enumerate(matches):
        rid = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i < len(matches) - 1 else len(cat_text_sin_fechas)
        block = cat_text_sin_fechas[start:end]
        years = re.findall(r"\b(18\d{2}|19\d{2}|20\d{2})\b", block)
        years = [int(y) for y in years if 1800 <= int(y) <= ANIO_ACTUAL]
        if years:
            year_dict[rid] = max(years)

    df_final = df_topo[df_topo["record_id"].isin(year_dict.keys())].copy()
    df_final["year"] = df_final["record_id"].map(year_dict)
    df_final["prestamos"] = 1

    if nunca_bytes:
        nunca_text = _decodificar_bytes(nunca_bytes)
        nunca_ids = {int(x) for x in re.findall(r"\b\d{7,}\b", nunca_text)}
        df_final.loc[df_final["record_id"].isin(nunca_ids), "prestamos"] = 0

    if mas2_bytes:
        mas2_text = _decodificar_bytes(mas2_bytes)
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

    # Ficha ISBD (autor/título completo/materias) a partir del catálogo.
    # Se cruza por record_id: solo se adjunta a libros que ya sobrevivieron
    # al filtro topo ∩ catálogo, así que un expurgado que aún constase en el
    # catálogo pero no en el topográfico (o viceversa) sigue sin aparecer.
    fichas_catalogo = _parsear_fichas_catalogo(cat_text)
    ids_validos = set(df_final["record_id"])
    fichas_filtradas = {rid: f for rid, f in fichas_catalogo.items() if rid in ids_validos}

    df_final["autor"] = df_final["record_id"].map(
        lambda rid: (fichas_filtradas.get(rid) or {}).get("autor") or ""
    )
    df_final["materias_texto"] = df_final["record_id"].map(
        lambda rid: " | ".join((fichas_filtradas.get(rid) or {}).get("materias") or [])
    )
    # El título del listado topográfico viene truncado a lo ancho de columna;
    # si el catálogo trae uno completo, lo preferimos.
    titulo_catalogo = df_final["record_id"].map(
        lambda rid: (fichas_filtradas.get(rid) or {}).get("titulo")
    )
    df_final["titulo"] = titulo_catalogo.where(titulo_catalogo.notna(), df_final["titulo"])

    return df_final, (len(df_topo) - len(df_final)), fichas_filtradas


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


def _sin_acentos(texto: str) -> str:
    """Quita diacríticos para que buscar 'poesia' encuentre 'poesía', etc."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _wildcard_contains_mask(series: pd.Series, patron: str) -> pd.Series:
    """Como _wildcard_mask pero busca la coincidencia en cualquier parte del
    texto (útil para título/autor/materia, donde no tiene sentido exigir que
    empiece justo por lo tecleado). Ignora acentos en ambos lados."""
    serie_norm = series.astype(str).map(_sin_acentos).str.upper()
    patron_norm = _sin_acentos(patron)
    regex_patron = re.escape(patron_norm).replace(r"\*", ".*")
    return serie_norm.str.contains(regex_patron, na=False, regex=True)


# ==========================================
# ENDPOINTS
# ==========================================
@app.get("/api/estado")
def estado():
    return {
        "db_lista": _db_status["ready"],
        "db_error": _db_status["error"],
        "descargando": _db_status["downloading"],
        "fts_activo": _db_status["fts"],
    }


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

    df, huerfanos, fichas = procesar_datos(topo_bytes, nunca_bytes, mas2_bytes, catalogo_bytes, tipo_analisis, num_caracteres)
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
        "poblacion": poblacion, "ts": time.time(), "fichas": fichas,
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


CAMPOS_BUSQUEDA_SIGNATURA = {
    "signatura": "signatura_real",
    "titulo": "titulo",
    "autor": "autor",
    "materia": "materias_texto",
}


def _texto_contains_mask(series: pd.Series, busqueda: str) -> pd.Series:
    """Máscara de coincidencia "contiene", insensible a mayúsculas y acentos,
    con soporte opcional de comodín "*". Usada para título/autor/materia
    tanto en el análisis por signatura como en recomendaciones específicas.
    Mayúsculas/acentos se normalizan aquí dentro, así que el llamador puede
    pasar la búsqueda tal cual la escribió el usuario."""
    busqueda = busqueda.strip().upper()
    if "*" in busqueda:
        return _wildcard_contains_mask(series, busqueda)
    serie_norm = series.astype(str).map(_sin_acentos).str.upper()
    return serie_norm.str.contains(re.escape(_sin_acentos(busqueda)), na=False)


@app.get("/api/analisis/signatura")
def signatura(
    session_id: str,
    seccion: str = "todo",
    busqueda: str = "",
    campo: str = "signatura",
    categoria: str = "Todas",
    sub: str = "Todas",
    prestamo: str = "todos",
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=5000),
):
    s = get_session(session_id)
    df = s["df"]

    if seccion == "adultos":
        df = df[~df["es_infantil"]]
    elif seccion == "infantil":
        df = df[df["es_infantil"]]

    busqueda = busqueda.strip().upper()
    if busqueda:
        columna = CAMPOS_BUSQUEDA_SIGNATURA.get(campo, "signatura_real")
        if columna == "signatura_real":
            # Signatura/CDU: se mantiene el filtrado por comodines "empieza por".
            df = df[_wildcard_mask(df[columna], busqueda)]
        else:
            # Título/autor/materia: coincidencia "contiene" (con soporte de
            # comodín "*" si el usuario lo usa igualmente).
            df = df[_texto_contains_mask(df[columna], busqueda)]

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


@app.get("/api/analisis/ficha")
def analisis_ficha(session_id: str, id_sistema: int):
    """Ficha catalográfica para un registro del análisis subido por el
    usuario, reconstruida a partir del propio fichero de catálogo (no de la
    base de datos de la red). A diferencia de /api/ficha/{id_sistema}, no
    incluye ejemplares en otras sucursales: aquí solo se analiza la
    biblioteca del usuario, así que esa sección no aporta nada."""
    s = get_session(session_id)
    df = s["df"]
    fila = df[df["record_id"] == id_sistema]
    if fila.empty:
        raise HTTPException(status_code=404, detail="Ese registro no está en el análisis actual.")
    row = fila.iloc[0]
    f = s.get("fichas", {}).get(id_sistema, {})

    return {
        "id_sistema": id_sistema,
        "titulo": row["titulo"],
        "autor": f.get("autor") or None,
        "signatura": row["signatura_real"],
        "cdu": row["categoria"],
        "anio": None if pd.isna(row["year"]) else int(row["year"]),
        "isbn": f.get("isbn"),
        "detalle_isbd": f.get("resto_isbd"),
        "materias": f.get("materias") or [],
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
            {"id_sistema": r.id_sistema, "titulo": r.titulo, "autor": r.autor, "anio": r.anio, "num_bibliotecas": int(r.total_bibliotecas)}
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
    "I0": "I0 · Bebeteca", "I1": "I1 · Hasta 8 años", "I2": "I2 · 8 a 10 años",
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


def _termino_fts(texto: str) -> str:
    """Prepara un término de búsqueda para MATCH sobre una tabla FTS5 con
    tokenizador 'trigram': se envuelve entre comillas dobles para que se
    interprete como una frase literal (equivale a un "contiene" tipo
    LIKE '%texto%'), escapando las comillas internas que pudiera traer."""
    return '"' + texto.replace('"', '""') + '"'


def _ids_con_materia_fallback(conn, ids_sistema: list, busqueda: str) -> set:
    """Respaldo en Python para bases de datos generadas ANTES de la
    migración FTS (sin materias_fts). Idéntico en resultado a la versión
    original, pero troceando ids_sistema en tandas de 900 para no superar
    el límite de parámetros de SQLite (SQLITE_MAX_VARIABLE_NUMBER = 999),
    que con catálogos grandes se podía sobrepasar y provocar un error."""
    if not ids_sistema:
        return set()
    busqueda_norm = _sin_acentos(busqueda.upper())
    encontrados = set()
    TAM_TANDA = 900
    for i in range(0, len(ids_sistema), TAM_TANDA):
        tanda = ids_sistema[i:i + TAM_TANDA]
        placeholders = ",".join("?" * len(tanda))
        try:
            filas = conn.execute(
                f"SELECT id_sistema, materia FROM materias WHERE id_sistema IN ({placeholders})",
                tanda,
            ).fetchall()
        except sqlite3.OperationalError:
            return set()
        encontrados.update(
            id_sistema for id_sistema, materia in filas
            if materia and busqueda_norm in _sin_acentos(materia.upper())
        )
    return encontrados


@app.get("/api/recomendaciones/cdu")
def recomendaciones_cdu(
    biblioteca: str,
    limite_cdu: int = 10,
    anio_minimo: int = 2015,
    campo: str = "cdu",
    busqueda: str = "",
    busqueda_cdu: str = "",  # compatibilidad con el nombre de parámetro anterior
):
    if biblioteca not in BIBLIOTECAS:
        raise HTTPException(status_code=400, detail="Biblioteca no reconocida.")
    conn = get_conn()

    # busqueda_cdu queda como alias retrocompatible: si un cliente antiguo
    # (sin el parámetro "campo") solo manda busqueda_cdu, se busca por CDU,
    # que ya es el valor por defecto de "campo".
    campo = (campo or "cdu").strip().lower()
    busqueda = (busqueda or busqueda_cdu or "").strip()

    # --------------------------------------------------------------------
    # Filtro por texto (materia/título/autor): si hay índices FTS5, se
    # resuelve ANTES del JOIN+GROUP BY, como una subconsulta MATCH dentro
    # del propio SQL. Así, cuando el usuario busca algo concreto, no hace
    # falta agrupar el catálogo completo de la red para luego descartar
    # casi todo en pandas: solo se agrupan los libros que ya coinciden.
    #
    # Si la .db es de antes de la migración FTS (no tiene materias_fts /
    # libros_fts), se cae al filtrado en Python de siempre (más lento,
    # pero funciona igual) para no romper despliegues con una base vieja.
    # --------------------------------------------------------------------
    filtro_sql = ""
    params_extra: list = []
    usar_fallback_materia = False
    usar_fallback_texto = False
    busqueda_norm = _sin_acentos(busqueda.upper()).strip() if busqueda else ""
    # El tokenizador 'trigram' de FTS5 indexa por fragmentos de 3 caracteres,
    # así que no admite buscar con 1-2 caracteres. Para esos casos (raros,
    # pero posibles) se usa el filtrado de respaldo en vez de fallar.
    fts_usable = _db_status["fts"] and len(busqueda_norm) >= 3 and "*" not in busqueda_norm

    if busqueda and campo == "materia":
        if fts_usable:
            filtro_sql = (
                "AND l.id_sistema IN "
                "(SELECT id_sistema FROM materias_fts WHERE materia_norm MATCH ?)"
            )
            params_extra = [_termino_fts(busqueda_norm)]
        else:
            usar_fallback_materia = True
    elif busqueda and campo in ("titulo", "autor"):
        if fts_usable:
            columna_fts = "titulo_norm" if campo == "titulo" else "autor_norm"
            filtro_sql = (
                f"AND l.id_sistema IN "
                f"(SELECT id_sistema FROM libros_fts WHERE {columna_fts} MATCH ?)"
            )
            params_extra = [_termino_fts(busqueda_norm)]
        else:
            usar_fallback_texto = True

    query_cdu = f"""
        SELECT l.id_sistema, l.titulo, l.autor, l.anio, l.cdu,
               COUNT(DISTINCT e.biblioteca) AS id_red_bibliotecas,
               GROUP_CONCAT(e.signatura, '||') AS todas_signaturas
        FROM libros l
        JOIN ejemplares e ON l.id_sistema = e.id_sistema
        WHERE l.id_sistema NOT IN (
            SELECT DISTINCT id_sistema FROM ejemplares WHERE UPPER(TRIM(biblioteca)) = ?
        )
        AND CAST(COALESCE(l.anio, 0) AS INTEGER) >= ?
        {filtro_sql}
        GROUP BY l.id_sistema, l.titulo, l.autor, l.anio, l.cdu
        HAVING id_red_bibliotecas > 0
    """
    params = [biblioteca.upper().strip(), int(anio_minimo)] + params_extra
    df = pd.read_sql_query(query_cdu, conn, params=params)
    if df.empty:
        return {"adultos": {}, "infantil": {}}

    if busqueda:
        if campo == "cdu":
            df = df[_wildcard_mask(df["cdu"], busqueda.upper())]
        elif usar_fallback_materia:
            ids_ok = _ids_con_materia_fallback(conn, df["id_sistema"].tolist(), busqueda)
            df = df[df["id_sistema"].isin(ids_ok)]
        elif usar_fallback_texto:
            columna = "titulo" if campo == "titulo" else "autor"
            df = df[_texto_contains_mask(df[columna], busqueda)]
        # si campo es "titulo"/"autor"/"materia" y sí hubo FTS, el filtro ya
        # se aplicó en SQL (filtro_sql) y no hace falta tocar nada más aquí.
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
        valores = [c.format_field().strip() for c in record.get_fields(tag)]
        if valores:
            campos_extra[etiqueta] = valores

    materias = [c.format_field().strip() for c in record.get_fields("650")]

    ejemplares = conn.execute(
        "SELECT biblioteca, seccion, signatura, codigo_barras FROM ejemplares WHERE id_sistema = ?",
        (id_sistema,),
    ).fetchall()

    campo_260 = record["260"] if "260" in record else None

    return {
        "id_sistema": id_sistema,
        "titulo": record.title,
        "autor": record.author,
        "isbn": record.isbn,
        "cdu": record["080"]["a"] if "080" in record and "a" in record["080"] else None,
        "lugar": campo_260["a"] if campo_260 and "a" in campo_260 else None,
        "editorial": campo_260["b"] if campo_260 and "b" in campo_260 else None,
        "anio": campo_260["c"] if campo_260 and "c" in campo_260 else None,
        "edicion": campos_extra.get("Edición", [None])[0],
        "descripcion_fisica": campos_extra.get("Descripción física", [None])[0],
        "serie": campos_extra.get("Serie", [None])[0],
        "notas": (campos_extra.get("Notas", []) + campos_extra.get("Contenido", []) + campos_extra.get("Resumen", [])),
        "materias": materias,
        "campos": campos_extra,
        "ejemplares": [
            {"biblioteca": r[0], "seccion": r[1], "signatura": r[2], "codigo_barras": r[3]}
            for r in ejemplares
        ],
    }


# ==========================================
# SERVIR LOS VÍDEOS DE AYUDA (backend/videos)
# ==========================================
VIDEOS_DIR = os.environ.get("VIDEOS_DIR", "/app/videos")
if os.path.isdir(VIDEOS_DIR):
    app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# ==========================================
# SERVIR EL FRONTEND ESTÁTICO
# ==========================================
FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "/app/frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
