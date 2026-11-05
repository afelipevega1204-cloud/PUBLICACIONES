# -*- coding: utf-8 -*-
"""
app.py — Boletín de Contratación para LinkedIn (Streamlit)
--------------------------------------------------------------------
- Izquierda: datos, textos de portada, colores y fondo.
- Derecha: vista previa en vivo (portada y páginas).
- "Guardar configuración" deja fijos edición, objetivo, textos, colores
  y fondo para la próxima vez que alguien abra la app.
--------------------------------------------------------------------
"""

import io
import os
import json
import base64
import datetime
import urllib.request

import pandas as pd
import streamlit as st
from PIL import Image

import motor_linkedin as motor

st.set_page_config(page_title="Boletín de Contratación · LinkedIn", page_icon="🏗️", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_CONFIG = os.path.join(BASE, "config_guardada.json")
RUTA_FONDO = os.path.join(BASE, "fondo_guardado.jpg")

ETIQUETAS_COLORES = {
    "color_fondo_portada": "Fondo azul de la portada",
    "color_texto_portada": "Texto de la portada (título y edición)",
    "color_acento": "Color de acento (naranja: OBJETIVO, botón, resaltados)",
    "color_texto_objetivo": "Texto del objetivo",
    "color_fondo_contenido": "Fondo de las páginas de contenido",
    "color_titulo_1": "Título “BOLETÍN DE”",
    "color_titulo_2": "Título “CONTRATACIÓN”",
    "color_barra_proyecto": "Barra con el nombre del proyecto",
    "color_texto_barra": "Texto de la barra del proyecto",
    "color_etiquetas": "Etiquetas (NO. PROCESO:, DEPARTAMENTO:…)",
    "color_valores": "Valores de cada campo",
    "color_pie": "Pie de página",
}
CAMPOS_TEXTO = ["edicion", "objetivo", "texto_boton", "fuente_datos"]


# =====================================================================
# Guardado permanente
#   1) Siempre se guarda en el servidor (config_guardada.json / fondo_guardado.jpg).
#   2) Si en Streamlit Cloud configuras los "Secrets" GITHUB_TOKEN y GITHUB_REPO,
#      además se guarda en tu repositorio de GitHub, y así nunca se pierde
#      aunque la app se reinicie.
# =====================================================================
def _github_disponible():
    try:
        return bool(st.secrets.get("GITHUB_TOKEN")) and bool(st.secrets.get("GITHUB_REPO"))
    except Exception:
        return False


def _subir_a_github(nombre_archivo, contenido_bytes, mensaje):
    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["GITHUB_REPO"]
    rama = st.secrets.get("GITHUB_BRANCH", "main")
    url = f"https://api.github.com/repos/{repo}/contents/{nombre_archivo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "User-Agent": "boletin-app"}
    sha = None
    try:
        req = urllib.request.Request(f"{url}?ref={rama}", headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            sha = json.loads(r.read())["sha"]
    except Exception:
        pass
    cuerpo = {"message": mensaje, "content": base64.b64encode(contenido_bytes).decode(), "branch": rama}
    if sha:
        cuerpo["sha"] = sha
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status in (200, 201)


def leer_config_guardada():
    cfg = dict(motor.CONFIG_DEFAULT)
    if os.path.exists(RUTA_CONFIG):
        try:
            with open(RUTA_CONFIG, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def leer_fondo_guardado():
    if os.path.exists(RUTA_FONDO):
        try:
            return Image.open(RUTA_FONDO).convert("RGB")
        except Exception:
            return None
    return None


def guardar_config_permanente(cfg):
    datos = {k: cfg[k] for k in motor.CONFIG_DEFAULT if k in cfg and k != "fecha_actualizacion"}
    contenido = json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")
    with open(RUTA_CONFIG, "wb") as f:
        f.write(contenido)
    if _github_disponible():
        _subir_a_github("config_guardada.json", contenido, "Actualiza configuración del boletín")
        return "servidor y GitHub"
    return "servidor"


def guardar_fondo_permanente(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    with open(RUTA_FONDO, "wb") as f:
        f.write(buf.getvalue())
    if _github_disponible():
        _subir_a_github("fondo_guardado.jpg", buf.getvalue(), "Actualiza fondo de portada")
        return "servidor y GitHub"
    return "servidor"


def borrar_fondo_permanente():
    if os.path.exists(RUTA_FONDO):
        os.remove(RUTA_FONDO)
    # En GitHub se reemplaza por una marca vacía (no se borra el historial)
    if _github_disponible():
        try:
            token = st.secrets["GITHUB_TOKEN"]; repo = st.secrets["GITHUB_REPO"]
            rama = st.secrets.get("GITHUB_BRANCH", "main")
            url = f"https://api.github.com/repos/{repo}/contents/fondo_guardado.jpg"
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                       "User-Agent": "boletin-app"}
            with urllib.request.urlopen(urllib.request.Request(f"{url}?ref={rama}", headers=headers)) as r:
                sha = json.loads(r.read())["sha"]
            cuerpo = json.dumps({"message": "Restaura fondo original", "sha": sha, "branch": rama}).encode()
            urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=headers, method="DELETE"))
        except Exception:
            pass


# =====================================================================
# Estado inicial de la sesión
# =====================================================================
def inicializar_estado(forzar=False):
    if forzar or "iniciado" not in st.session_state:
        cfg = leer_config_guardada()
        for k, v in cfg.items():
            if k != "fecha_actualizacion":
                st.session_state[k] = v
        st.session_state["fondo"] = leer_fondo_guardado()
        st.session_state["fondo_es_nuevo"] = False
        st.session_state["iniciado"] = True


def config_actual():
    cfg = {k: st.session_state.get(k, v) for k, v in motor.CONFIG_DEFAULT.items()}
    fecha = st.session_state.get("fecha")
    cfg["fecha_actualizacion"] = fecha.strftime("%d/%m/%Y") if fecha else ""
    return cfg


inicializar_estado()


def restaurar_fabrica():
    for k, v in motor.CONFIG_DEFAULT.items():
        if k != "fecha_actualizacion":
            st.session_state[k] = v
    st.session_state["fondo"] = None
    st.session_state["fondo_es_nuevo"] = True
    st.session_state.pop("firma_fondo", None)


# =====================================================================
# Datos y renderizado (con caché para que la vista previa sea rápida)
# =====================================================================
@st.cache_data(ttl=300, show_spinner=False)
def obtener_datos(link):
    return motor.cargar_datos(link)


def _fondo_bytes(img):
    if img is None:
        return b""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


@st.cache_data(show_spinner=False, max_entries=20)
def render_portada(cfg_json, fondo_bytes):
    fondo = Image.open(io.BytesIO(fondo_bytes)) if fondo_bytes else None
    return motor.generar_portada(json.loads(cfg_json), fondo)


@st.cache_data(show_spinner=False, max_entries=40)
def render_pagina(filas_json, cfg_json):
    cfg = json.loads(cfg_json)
    fecha = cfg["fecha_actualizacion"] or datetime.date.today().strftime("%d/%m/%Y")
    return motor.generar_pagina(json.loads(filas_json), cfg, fecha)


def paginas_de(df, n):
    filas = df.to_dict("records")
    return [filas[i:i + n] for i in range(0, len(filas), n)]


# =====================================================================
# Interfaz
# =====================================================================
st.markdown(
    "<h2 style='margin-bottom:0'>🏗️ Boletín de Contratación · LinkedIn</h2>"
    "<p style='color:#666;margin-top:4px'>Edita a la izquierda y mira el resultado a la derecha. "
    "Lo que guardes queda fijo para la próxima vez.</p>",
    unsafe_allow_html=True,
)

col_izq, col_der = st.columns([1, 1.15], gap="large")

with col_izq:
    tab_datos, tab_portada, tab_colores, tab_fondo = st.tabs(
        ["📊 Datos", "📝 Portada", "🎨 Colores", "🖼️ Fondo"])

    # ---------------- DATOS ----------------
    with tab_datos:
        link = st.text_input(
            "Enlace de Google Sheets (pestaña BOLETIN_CANVA)",
            key="link",
            placeholder="https://docs.google.com/spreadsheets/d/.../edit?gid=...",
            help="Pega el enlace normal de la pestaña; la app lo convierte sola. "
                 "La hoja debe estar compartida como 'Cualquier persona con el enlace - Lector'.",
        )
        c1, c2 = st.columns(2)
        with c1:
            st.date_input("Fecha de actualización", value=datetime.date.today(), key="fecha",
                          format="DD/MM/YYYY")
        with c2:
            st.number_input("Proyectos por página", min_value=1, max_value=6, step=1,
                            key="proyectos_por_pagina")
        if st.button("🔄 Volver a leer la hoja", help="Úsalo si acabas de cambiar datos en Google Sheets"):
            obtener_datos.clear()

    # ---------------- PORTADA ----------------
    with tab_portada:
        st.text_input("Número de edición", key="edicion")
        st.text_area("Objetivo", key="objetivo", height=150,
                     help="Encierra palabras entre *asteriscos* para resaltarlas en naranja y negrilla.")
        st.text_area("Texto del botón", key="texto_boton", height=90,
                     help="Usa | para forzar un salto de línea y *asteriscos* para resaltar.")
        st.text_input("Fuente de los datos (pie de página)", key="fuente_datos")
        st.caption("💡 `*palabra*` = resaltado · `|` = salto de línea")

    # ---------------- COLORES ----------------
    with tab_colores:
        st.caption("Si no cambias nada, se mantienen los colores del diseño original.")
        cc1, cc2 = st.columns(2)
        for i, (clave, etiqueta) in enumerate(ETIQUETAS_COLORES.items()):
            with (cc1 if i % 2 == 0 else cc2):
                st.color_picker(etiqueta, key=clave)

    # ---------------- FONDO ----------------
    with tab_fondo:
        st.caption("La foto ocupa la parte superior de la portada. Funcionan mejor imágenes "
                   "horizontales y de buena resolución (mínimo 1600 px de ancho).")
        archivo = st.file_uploader("Subir nueva imagen de fondo", type=["jpg", "jpeg", "png", "webp"])
        if archivo is not None:
            firma = (archivo.name, archivo.size)
            if st.session_state.get("firma_fondo") != firma:
                st.session_state["fondo"] = Image.open(archivo).convert("RGB")
                st.session_state["fondo_es_nuevo"] = True
                st.session_state["firma_fondo"] = firma
        if st.session_state.get("fondo") is not None:
            st.image(st.session_state["fondo"], caption="Fondo en uso", width="stretch")
        else:
            st.info("Se está usando el fondo original.")
        if st.button("↩️ Volver al fondo original"):
            st.session_state["fondo"] = None
            st.session_state["fondo_es_nuevo"] = True
            st.session_state.pop("firma_fondo", None)
            st.rerun()

    # ---------------- GUARDAR ----------------
    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        if st.button("💾 Guardar configuración", type="primary", width="stretch",
                     help="Deja fijos edición, objetivo, textos, colores y fondo"):
            try:
                donde = guardar_config_permanente(config_actual())
                if st.session_state.get("fondo_es_nuevo"):
                    if st.session_state.get("fondo") is None:
                        borrar_fondo_permanente()
                    else:
                        guardar_fondo_permanente(st.session_state["fondo"])
                    st.session_state["fondo_es_nuevo"] = False
                st.success(f"Configuración guardada en el {donde}.")
            except Exception as e:
                st.error(f"No se pudo guardar: {e}")
    with g2:
        st.button("↺ Descartar cambios", width="stretch",
                  help="Vuelve a la última configuración guardada",
                  on_click=inicializar_estado, kwargs={"forzar": True})
    with st.expander("Restaurar diseño original de fábrica"):
        st.write("Vuelve todos los textos, colores y el fondo a los del diseño original. "
                 "Luego presiona **Guardar configuración** si quieres dejarlo fijo.")
        st.button("Restaurar valores de fábrica", on_click=restaurar_fabrica)
    if not _github_disponible():
        st.caption("ℹ️ El guardado es en el servidor de la app. Para que nunca se pierda aunque la app "
                   "se reinicie, configura los *Secrets* de GitHub (ver README).")

# =====================================================================
# VISTA PREVIA (derecha)
# =====================================================================
with col_der:
    cfg = config_actual()
    cfg_json = json.dumps(cfg, ensure_ascii=False, sort_keys=True)
    fondo_b = _fondo_bytes(st.session_state.get("fondo"))

    df, error = None, None
    if link.strip():
        try:
            with st.spinner("Leyendo Google Sheets..."):
                df = obtener_datos(link)
        except Exception as e:
            error = str(e)

    bloques = paginas_de(df, int(cfg["proyectos_por_pagina"])) if df is not None else []
    opciones = ["Portada"] + [f"Página {i + 1}" for i in range(len(bloques))]

    st.markdown("#### 👁️ Vista previa")
    if error:
        st.error("No se pudo leer la hoja. Revisa que el enlace sea de la pestaña BOLETIN_CANVA y que "
                 f"esté compartida como 'Cualquier persona con el enlace'.\n\nDetalle: {error}")
    elif df is None:
        st.info("Pega el enlace de Google Sheets en la pestaña **Datos** para ver también las páginas "
                "de contenido. Mientras tanto puedes editar la portada.")
    else:
        st.caption(f"{len(df)} proyectos → 1 portada + {len(bloques)} página(s)")

    vista = st.radio("Página", opciones, horizontal=True, label_visibility="collapsed")

    with st.spinner("Actualizando vista previa..."):
        if vista == "Portada":
            img = render_portada(cfg_json, fondo_b)
        else:
            idx = opciones.index(vista) - 1
            img = render_pagina(json.dumps(bloques[idx], ensure_ascii=False), cfg_json)
    st.image(img, width="stretch")

    # ---------------- DESCARGAS ----------------
    st.markdown("#### ⬇️ Descargar")
    if df is None:
        st.button("Generar todas las imágenes", disabled=True, width="stretch",
                  help="Primero pega el enlace de Google Sheets")
    else:
        if st.button("🚀 Generar todas las imágenes", type="primary", width="stretch"):
            with st.spinner("Generando todas las páginas..."):
                paginas = [render_portada(cfg_json, fondo_b)] + [
                    render_pagina(json.dumps(b, ensure_ascii=False), cfg_json) for b in bloques]
                st.session_state["zip"] = motor.exportar_zip(paginas)
                st.session_state["n_paginas"] = len(paginas)
        if st.session_state.get("zip"):
            st.download_button(
                f"📦 Descargar ZIP ({st.session_state['n_paginas']} imágenes PNG + PDF carrusel)",
                data=st.session_state["zip"],
                file_name=f"Boletin_LinkedIn_{datetime.date.today():%Y%m%d}.zip",
                mime="application/zip", width="stretch")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    st.download_button(f"🖼️ Descargar solo esta imagen ({vista})", data=buf.getvalue(),
                       file_name=f"{vista.replace(' ', '_').lower()}.png", mime="image/png",
                       width="stretch")
