"""Estilo visual de HERMES, compartido por todas las pantallas."""
import html

import streamlit as st

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MENORES = {"y", "de", "del", "la", "las", "los", "e"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..100,400..800&display=swap');
:root {
  --h-azul: #0B4F9C; --h-azul-hondo: #083A75; --h-tinta: #0E2340; --h-suave: #51627E;
  --h-fondo: #EEF2F8; --h-superficie: #FFFFFF; --h-linea: #D9E2EF; --h-celeste: #DCE8F7;
  --h-ambar: #E9A23B; --h-ambar-suave: #FCF1DF; --h-ambar-texto: #8A5A00;
  --h-rojo: #C2362F; --h-rojo-suave: #FBE7E5; --h-verde: #1F8A5B; --h-verde-suave: #E3F3EB;
}
html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp td, .stApp th, .stApp div[data-testid="stMarkdownContainer"] {
  font-family: "Archivo", "Segoe UI", system-ui, sans-serif;
}
.stApp { background: var(--h-fondo); }
.stApp h1 { font-stretch: 75%; font-weight: 800; letter-spacing: 0.01em; color: var(--h-tinta); }
.stApp h2, .stApp h3 { font-weight: 700; color: var(--h-tinta); }
section[data-testid="stSidebar"] { background: var(--h-superficie); border-right: 1px solid var(--h-linea); }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--h-celeste); }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: var(--h-azul); font-weight: 700; }
.stButton button, .stDownloadButton button, .stFormSubmitButton button { border-radius: 10px; font-weight: 700; }
div[data-testid="stExpander"] details, div[data-testid="stForm"] { border-radius: 14px; background: var(--h-superficie); }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }

/* Piezas comunes */
.h-sub { color: var(--h-suave); margin: -0.6rem 0 1.2rem; }
.h-panel { background: var(--h-superficie); border: 1px solid var(--h-linea); border-radius: 14px; padding: 18px 20px; }
.h-panel h3 { margin: 0 0 10px; font-size: 1rem; }
.h-estado { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
.h-estado.ok { background: var(--h-verde-suave); color: var(--h-verde); }
.h-estado.espera { background: var(--h-ambar-suave); color: var(--h-ambar-texto); }
.h-estado.no { background: var(--h-rojo-suave); color: var(--h-rojo); }
.h-estado.info { background: var(--h-celeste); color: var(--h-azul); }

/* Tarjeta de usuario en el menú */
.h-usuario { display: flex; gap: 10px; align-items: center; padding: 10px 4px 4px; border-top: 1px solid var(--h-linea); }
.h-iniciales { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: var(--h-azul); color: #FFFFFF; font-weight: 700; font-size: 0.85rem; }
.h-usuario b { display: block; line-height: 1.2; color: var(--h-tinta); }
.h-usuario small { color: var(--h-suave); }

@media (prefers-color-scheme: dark) {
  :root { --h-tinta: #E7EEF8; --h-suave: #A3B3CB; --h-fondo: #0A1628; --h-superficie: #11203A; --h-linea: #22355A;
          --h-celeste: #1A3157; --h-ambar-suave: #3A2C14; --h-ambar-texto: #E9A23B; --h-rojo-suave: #3A1A1A;
          --h-verde-suave: #12301F; }
}
</style>
"""


def aplicar():
    """Carga el estilo de HERMES en la página (se llama una vez en app.py)."""
    st.markdown(CSS, unsafe_allow_html=True)


def bonito(texto):
    """'PEREZ LOPEZ, ANA' -> 'Perez Lopez, Ana'; deja en minúscula y, de, del..."""
    palabras = str(texto or "").title().split(" ")
    return " ".join(w.lower() if i and w.lower() in MENORES else w for i, w in enumerate(palabras))


def nombre_pila(nombre_completo):
    """'PEREZ LOPEZ, ANA MARIA' -> 'Ana'."""
    partes = str(nombre_completo or "").split(",")
    nombres = (partes[1] if len(partes) > 1 else partes[0]).split()
    return nombres[0].title() if nombres else ""


def iniciales(nombre):
    t = str(nombre or "").replace(",", " ").split()
    if "," in str(nombre or ""):  # "APELLIDO APELLIDO, NOMBRE" -> N + A
        ap, _, no = str(nombre).partition(",")
        t = [no.split()[0] if no.split() else "", ap.split()[0] if ap.split() else ""]
    return "".join(x[0] for x in t if x)[:2].upper() or "?"


def fecha_larga(d):
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def estado_html(texto, tipo):
    return f'<span class="h-estado {tipo}">{html.escape(texto)}</span>'


def tarjeta_usuario(nombre, detalle):
    st.sidebar.markdown(
        f'<div class="h-usuario"><span class="h-iniciales">{html.escape(iniciales(nombre))}</span>'
        f'<div><b>{html.escape(nombre)}</b><small>{html.escape(detalle)}</small></div></div>',
        unsafe_allow_html=True,
    )
