import calendar
import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db

from reglas_vacaciones import (  # las reglas viven en reglas_vacaciones.py
    DIAS_BLOQUE, DIAS_PERIODO, MESES_NORMALES, MESES_CICLO, TOPE_POR_GRUPO, TOPE_EJEC_SERVICIOS,
    sumar_meses, aniversario, primer_aniversario, inicio_ciclo, usados_en_ciclo, es_retail,
)


def cargar_personal():
    return db.consultar("SELECT * FROM rrhh_personal ORDER BY nombre")


def solicitudes(solo_activas=False):
    df = db.consultar(
        """SELECT s.*, p.nombre, p.puesto, p.departamento, p.area, p.seccion
           FROM vacaciones_solicitudes s JOIN rrhh_personal p ON p.cod = s.cod
           ORDER BY s.inicio DESC"""
    )
    if solo_activas:
        df = df[df["estado"] != "RECHAZADA"]
    return df


def max_simultaneos(df, ini, fin):
    mayor, d = 0, ini
    while d <= fin:
        iso = d.isoformat()
        n = int(((df["inicio"] <= iso) & (df["fin"] >= iso)).sum())
        mayor = max(mayor, n)
        d += timedelta(days=1)
    return mayor


def meses_entre(ini, fin):
    """Primer y último día de cada mes que toca el rango."""
    meses, d = [], ini.replace(day=1)
    while d <= fin:
        ultimo = d.replace(day=calendar.monthrange(d.year, d.month)[1])
        meses.append((d, ultimo))
        d = ultimo + timedelta(days=1)
    return meses


MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def validar(p, ingreso, ini, fin, es_admin):
    """Devuelve (errores, requiere_gerencia, bloque)."""
    if fin < ini:
        return ["La fecha final es anterior a la inicial."], False, None
    errores, gerencia = [], False
    dias = (fin - ini).days + 1
    if ini < db.hoy() and not es_admin:
        errores.append("La fecha de inicio ya pasó. Elige una fecha desde hoy.")

    c_ini = inicio_ciclo(ingreso, ini)
    c_hoy = inicio_ciclo(ingreso, db.hoy())
    if c_ini is None:
        return [f"Solo se puede tomar vacaciones después de cumplir 1 año en la empresa "
                f"(desde el {primer_aniversario(ingreso):%d/%m/%Y})."], False, None
    if not es_admin and (c_hoy is None or c_ini > c_hoy):
        return ["Esas fechas corresponden a tu próximo periodo. Podrás programarlas "
                "cuando se renueven tus días, al cumplir un año más en la empresa."], False, None
    limite = sumar_meses(c_ini, MESES_NORMALES)
    tope = sumar_meses(c_ini, MESES_CICLO)
    if fin >= tope:
        errores.append("Estas fechas pasan el plazo máximo de tu periodo. Elige fechas más cercanas.")
    elif fin > limite:
        gerencia = True

    activas = solicitudes(solo_activas=True)
    usados = usados_en_ciclo(activas, p["cod"], c_ini, tope)
    libres = DIAS_PERIODO - usados[1] - usados[2]
    bloque = 1  # los 30 días se reparten libremente; el bloque se guarda solo por compatibilidad
    if dias > libres:
        errores.append(f"Te quedan {libres} días por programar y estás pidiendo {dias}.")

    propias = activas[activas["cod"] == p["cod"]]
    if max_simultaneos(propias, ini, fin) > 0:
        errores.append("Ya tienes vacaciones registradas que se cruzan con esas fechas.")

    if es_retail(p):
        otros = activas[(activas["cod"] != p["cod"]) & activas.apply(es_retail, axis=1)] if not activas.empty \
            else activas
        # Grupos: máximo 1 persona del grupo de vacaciones a la vez
        if str(p["seccion"]).upper().startswith("GRUPO"):
            grupo = otros[otros["seccion"] == p["seccion"]]
            if max_simultaneos(grupo, ini, fin) >= TOPE_POR_GRUPO:
                errores.append("Alguien de tu grupo ya tiene vacaciones en esas fechas. Prueba con otras.")
        # Ejecutivos de servicios: máximo 2 en el mismo mes, en fechas que no se crucen
        if str(p["puesto"]).upper() == "EJECUTIVO DE SERVICIOS":
            ejec = otros[otros["puesto"].str.upper() == "EJECUTIVO DE SERVICIOS"]
            if max_simultaneos(ejec, ini, fin) > 0:
                errores.append("Otro ejecutivo de servicios ya tiene vacaciones en esas fechas. "
                               "Deben salir en fechas distintas.")
            for m_ini, m_fin in meses_entre(ini, fin):
                en_mes = ejec[(ejec["inicio"] <= m_fin.isoformat()) & (ejec["fin"] >= m_ini.isoformat())]
                if en_mes["cod"].nunique() >= TOPE_EJEC_SERVICIOS:
                    errores.append(f"En {MESES_ES[m_ini.month - 1]} ya salen {TOPE_EJEC_SERVICIOS} ejecutivos de "
                                   "servicios de vacaciones (es el máximo por mes). Prueba con otro mes.")
    return errores, gerencia, bloque


# ---------- Estilo ----------
st.markdown(
    """
<style>
.vac-banda {
  background: #0B4F9C; color: #FFFFFF; border-radius: 14px;
  padding: 1.4rem 1.6rem; display: flex; justify-content: space-between;
  align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.9rem;
}
.vac-banda h2 { color: #FFFFFF; margin: 0; padding: 0; font-size: 1.45rem; font-weight: 600; }
.vac-banda p { margin: 0.25rem 0 0; opacity: 0.85; font-size: 0.95rem; }
.vac-saldo { text-align: right; line-height: 1; }
.vac-saldo b { font-size: 3.2rem; font-weight: 700; display: block; }
.vac-saldo span { font-size: 0.95rem; opacity: 0.85; }
.vac-dias { display: flex; gap: 4px; margin: 0.2rem 0 0.4rem; }
.vac-dias i { flex: 1; height: 16px; border-radius: 3px; border: 1px solid #0B4F9C; }
.vac-dias i.tomado { background: #0B4F9C; }
.vac-dias i.pendiente { background: #9DBDE6; border-color: #9DBDE6; }
.vac-dias i.libre { background: #FFFFFF; }
.vac-leyenda { font-size: 0.85rem; color: #4A5D7E; margin-bottom: 1rem; }
.vac-leyenda em { font-style: normal; display: inline-block; width: 10px; height: 10px;
  border-radius: 2px; margin: 0 4px 0 12px; vertical-align: -1px; border: 1px solid #0B4F9C; }
</style>
""",
    unsafe_allow_html=True,
)


# ---------- Pantalla ----------
st.title("Vacaciones")
sesion = st.session_state.get("sesion", {})
es_admin = sesion.get("rol") == "admin"

personal = cargar_personal()
if personal.empty:
    st.info("Todavía no hay personal cargado. El administrador debe cargar el Excel.")
    st.stop()

if es_admin:
    etiquetas = {f"{r.nombre} ({r.cod})": r.cod for r in personal.itertuples()}
    cod = etiquetas[st.selectbox("Registrar vacaciones de", list(etiquetas.keys()))]
else:
    cod = sesion.get("cod")
    if not cod:
        st.warning("Tu usuario todavía no está asociado a tu ficha de personal. "
                   "Pide al administrador que lo asocie en Perfiles.")
        st.stop()

fila = personal[personal["cod"] == cod]
if fila.empty:
    st.warning("No encontré tu ficha en el personal cargado. Avisa al administrador.")
    st.stop()
p = fila.iloc[0]

try:
    ingreso = date.fromisoformat(str(p["f_ingreso"]))
except ValueError:
    st.error("La fecha de ingreso registrada no es válida. Pide al administrador que la revise.")
    st.stop()

hoy = db.hoy()
c_ini = inicio_ciclo(ingreso, hoy)
if c_ini is None:
    primero = primer_aniversario(ingreso)
    if not es_admin:
        st.markdown(
            f"""<div class="vac-banda">
  <div><h2>{html.escape(str(p["nombre"]))}</h2>
  <p>Podrás programar tus vacaciones desde el {primero:%d/%m/%Y}, cuando cumplas 1 año en la empresa.</p></div>
</div>""",
            unsafe_allow_html=True,
        )
        st.stop()
    st.info(f"Esta persona todavía no cumple 1 año en la empresa. "
            f"Solo se pueden registrar vacaciones desde el {primero:%d/%m/%Y}.")
    c_ini = primero
limite = sumar_meses(c_ini, MESES_NORMALES)
tope = sumar_meses(c_ini, MESES_CICLO)
activas = solicitudes(solo_activas=True)
usados = usados_en_ciclo(activas, p["cod"], c_ini, tope)
en_ciclo = activas[(activas["cod"] == p["cod"]) & (activas["inicio"] >= c_ini.isoformat()) & (activas["inicio"] < tope.isoformat())]
tomados = int(en_ciclo[en_ciclo["estado"] == "APROBADA"]["dias"].sum())
total = DIAS_PERIODO
libres = max(total - usados[1] - usados[2], 0)
pendientes = max(total - libres - tomados, 0)

# Banda con el nombre y los días disponibles
nombre = html.escape(str(p["nombre"]))
detalle = html.escape(f"{p['puesto']}, {p['area'] or p['departamento']}".title())
st.markdown(
    f"""<div class="vac-banda">
  <div><h2>{nombre}</h2><p>{detalle}</p></div>
  <div class="vac-saldo"><b>{libres}</b><span>días por programar de {total}</span></div>
</div>""",
    unsafe_allow_html=True,
)
cuadros = "".join(
    f'<i class="{c}"></i>' for c in ["tomado"] * tomados + ["pendiente"] * pendientes + ["libre"] * libres
)
st.markdown(
    f"""<div class="vac-dias">{cuadros}</div>
<div class="vac-leyenda"><em style="background:#0B4F9C"></em>aprobados
<em style="background:#9DBDE6;border-color:#9DBDE6"></em>en espera
<em style="background:#FFFFFF"></em>disponibles</div>""",
    unsafe_allow_html=True,
)

# Alertas del periodo (sin mostrar fechas límite)
if libres == 0:
    st.success("Ya programaste todos tus días de este periodo. "
               "Se renovarán cuando cumplas un año más en la empresa.")
elif hoy > limite:
    st.warning("Tus días por programar ya pasaron el plazo normal. "
               "Las solicitudes que hagas ahora necesitarán aprobación de gerencia.")
elif (limite - hoy).days <= 60:
    st.info(f"Te quedan {libres} días por programar y el plazo para tomarlos se acerca. "
            "Te recomendamos programarlos pronto.")

# Nueva solicitud: las alertas aparecen mientras eliges las fechas
st.subheader("Programar vacaciones")
d1, d2 = st.columns(2)
ini = d1.date_input("Desde", value=hoy, format="DD/MM/YYYY")
fin = d2.date_input("Hasta", value=hoy + timedelta(days=6), format="DD/MM/YYYY")

errores, gerencia, bloque = validar(p, ingreso, ini, fin, es_admin)
dias = (fin - ini).days + 1
if dias > 0:
    st.markdown(f"Estás pidiendo **{dias} {'día' if dias == 1 else 'días'}**, "
                f"del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}.")
for e in errores:
    st.error(e)
if gerencia and not errores:
    st.warning("Estas fechas necesitan aprobación de gerencia, así que la respuesta puede demorar un poco más.")

if st.button("Solicitar vacaciones", type="primary", disabled=bool(errores)):
    errores, gerencia, bloque = validar(p, ingreso, ini, fin, es_admin)  # se revisa otra vez al guardar
    if errores:
        for e in errores:
            st.error(e)
    else:
        db.ejecutar(
            "INSERT INTO vacaciones_solicitudes (cod, inicio, fin, dias, bloque, estado, requiere_gerencia, creado) "
            "VALUES (:cod, :inicio, :fin, :dias, :bloque, :estado, :rg, :creado)",
            {
                "cod": str(p["cod"]), "inicio": ini.isoformat(), "fin": fin.isoformat(),
                "dias": dias, "bloque": int(bloque),
                "estado": "PENDIENTE_GERENCIA" if gerencia else "PENDIENTE",
                "rg": int(gerencia), "creado": db.ahora(),
            },
        )
        st.session_state["vac_ok"] = gerencia
        st.rerun()

if "vac_ok" in st.session_state:
    if st.session_state.pop("vac_ok"):
        st.success("Solicitud enviada. Como necesita aprobación de gerencia, puede tardar un poco más.")
    else:
        st.success("Solicitud enviada. Puedes ver su estado abajo, en Mis solicitudes.")

# Historial
st.subheader("Mis solicitudes")
ESTADOS = {
    "PENDIENTE": "En espera",
    "PENDIENTE_GERENCIA": "En espera de gerencia",
    "APROBADA": "Aprobada",
    "RECHAZADA": "Rechazada",
}
hist = solicitudes()
hist = hist[hist["cod"] == p["cod"]]
if hist.empty:
    st.caption("Todavía no tienes solicitudes.")
else:
    vista = pd.DataFrame({
        "Desde": pd.to_datetime(hist["inicio"]).dt.strftime("%d/%m/%Y"),
        "Hasta": pd.to_datetime(hist["fin"]).dt.strftime("%d/%m/%Y"),
        "Días": hist["dias"],
        "Estado": hist["estado"].map(ESTADOS).fillna(hist["estado"]),
        "Respondió": hist["resuelto_por"].fillna(""),
    })
    st.dataframe(vista, width="stretch", hide_index=True)
