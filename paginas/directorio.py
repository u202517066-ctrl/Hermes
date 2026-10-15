import html
from datetime import date

import pandas as pd
import streamlit as st

import db
import estilo

st.title("Directorio")


@st.cache_data(ttl=600)
def cargar():
    return db.consultar("SELECT * FROM rrhh_personal ORDER BY nombre")


df = cargar()
hoy = db.hoy()
iso = hoy.isoformat()

# Quién está fuera hoy (vacaciones aprobadas o teletrabajo)
vac = db.consultar("SELECT cod FROM vacaciones_solicitudes WHERE estado = 'APROBADA' AND inicio <= :h AND fin >= :h",
                   {"h": iso})
tele = db.consultar("SELECT cod FROM teletrabajo_solicitudes WHERE estado = 'APROBADO' AND fecha = :h", {"h": iso})
hoy_estado = {**{c: "Teletrabajo" for c in tele["cod"]}, **{c: "De vacaciones" for c in vac["cod"]}}

c1, c2, c3 = st.columns([1.3, 1, 1.6])
area = c1.selectbox("Área", ["Todas las áreas"] + sorted(df["area"].dropna().unique().tolist()), label_visibility="collapsed")
grupos = sorted(df[df["seccion"].fillna("").str.upper().str.startswith("GRUPO")]["seccion"].unique().tolist())
seccion = c2.selectbox("Grupo", ["Todos los grupos"] + grupos, label_visibility="collapsed",
                       format_func=lambda g: g.replace("_", " ").title() if g != "Todos los grupos" else g)
buscar = c3.text_input("Buscar", placeholder="Buscar por nombre, puesto o código", label_visibility="collapsed")

if area != "Todas las áreas":
    df = df[df["area"] == area]
if seccion != "Todos los grupos":
    df = df[df["seccion"] == seccion]
if buscar:
    b = buscar.strip().lower()
    df = df[df[["nombre", "puesto", "cod"]].fillna("").apply(lambda r: b in " ".join(r).lower(), axis=1)]

fuera = sum(1 for c in df["cod"] if c in hoy_estado)
st.markdown(f'<div class="h-sub" style="margin-top:4px">{len(df)} {"persona" if len(df) == 1 else "personas"}'
            + (f"; hoy {fuera} {'está' if fuera == 1 else 'están'} de vacaciones o en teletrabajo." if fuera else ".")
            + "</div>", unsafe_allow_html=True)


def ingreso(v):
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def antiguedad(d):
    if not d:
        return ""
    anios = hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
    return f"{anios} {'año' if anios == 1 else 'años'}" if anios else "Menos de 1 año"


fechas = df["f_ingreso"].map(ingreso)
tabla = pd.DataFrame({
    "Nombre": df["nombre"].map(estilo.bonito),
    "Puesto": df["puesto"].map(estilo.bonito),
    "Área": df["area"].map(estilo.bonito),
    "Grupo o sección": df["seccion"].fillna("").map(lambda s: s.replace("_", " ").title() if s.upper().startswith("GRUPO") else estilo.bonito(s)),
    "Sede": df["sede"].fillna("").map(estilo.bonito),
    "Ingreso": fechas.map(lambda d: d.strftime("%d/%m/%Y") if d else ""),
    "Antigüedad": fechas.map(antiguedad),
    "Hoy": df["cod"].map(lambda c: hoy_estado.get(c, "")),
    "Código": df["cod"],
})
st.dataframe(tabla, width="stretch", hide_index=True, height=min(38 + 35 * max(len(tabla), 1), 640),
             column_config={"Nombre": st.column_config.TextColumn(width="medium"),
                            "Área": st.column_config.TextColumn(width="medium")})
st.download_button("Descargar la lista (CSV para Excel)", data=tabla.to_csv(index=False, sep=";").encode("utf-8-sig"),
                   file_name=f"directorio_{iso}.csv", mime="text/csv")
