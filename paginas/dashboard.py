import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
import estilo
from reglas_vacaciones import jefes_por_area

st.title("Indicadores")
sesion = st.session_state.get("sesion", {})
rol, mi_cod = sesion.get("rol"), sesion.get("cod")
if rol not in ("jefe", "admin"):
    st.info("Esta pantalla es para jefaturas. Tu resumen está en Inicio.")
    st.stop()

st.markdown(
    """
<style>
.d-lista { list-style: none; margin: 0; padding: 0; }
.d-lista li { display: grid; grid-template-columns: 50px 1fr auto; gap: 12px; align-items: center; padding: 9px 0;
  border-bottom: 1px solid var(--h-linea); }
.d-lista li:last-child { border-bottom: 0; }
.d-dia { text-align: center; border-radius: 10px; background: var(--h-fondo); padding: 4px 0; line-height: 1.1; color: var(--h-tinta); }
.d-dia b { display: block; font-size: 1.25rem; font-stretch: 75%; }
.d-dia small { font-size: 0.72rem; color: var(--h-suave); }
.d-lista p { margin: 0; font-weight: 600; color: var(--h-tinta); }
.d-lista p small { display: block; font-weight: 400; color: var(--h-suave); }
.d-vacio { color: var(--h-suave); margin: 0; }
.st-key-d_grafico { background: var(--h-superficie); margin-top: 6px; }
</style>
""",
    unsafe_allow_html=True,
)

hoy = db.hoy()
personal = db.consultar("SELECT cod, nombre, area, seccion FROM rrhh_personal")
if rol == "jefe":
    areas = [a for a, c in jefes_por_area(personal).items() if c == mi_cod]
    if not areas:
        yo = personal[personal["cod"] == mi_cod]
        areas = list(yo["area"]) if not yo.empty else []
    personal = personal[personal["area"].isin(areas)]
    alcance = ", ".join(estilo.bonito(a) for a in areas) or "tu equipo"
else:
    alcance = "toda la empresa"
st.markdown(f'<div class="h-sub">Resumen de {html.escape(alcance)} al {estilo.fecha_larga(hoy).lower()}.</div>',
            unsafe_allow_html=True)

cods = set(personal["cod"])
vac = db.consultar("SELECT cod, inicio, fin, dias, estado FROM vacaciones_solicitudes WHERE estado <> 'RECHAZADA'")
vac = vac[vac["cod"].isin(cods)].merge(personal, on="cod")
tele = db.consultar("SELECT cod, fecha, estado FROM teletrabajo_solicitudes WHERE estado <> 'RECHAZADO'")
tele = tele[tele["cod"].isin(cods)].merge(personal, on="cod")
iso = hoy.isoformat()

en_espera = vac[vac["estado"].str.startswith("PENDIENTE")]
fuera_hoy = vac[(vac["estado"] == "APROBADA") & (vac["inicio"] <= iso) & (vac["fin"] >= iso)]
tele_mes = tele[tele["fecha"].str.startswith(iso[:7], na=False)]
tele_hoy = tele[tele["fecha"] == iso]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Personas", len(personal))
c2.metric("Vacaciones en espera", len(en_espera))
c3.metric("De vacaciones hoy", fuera_hoy["cod"].nunique())
c4.metric("Teletrabajo este mes", f"{len(tele_mes)} {'día' if len(tele_mes) == 1 else 'días'}")


def fc(i):
    d = date.fromisoformat(i)
    return f"{d.day} de {estilo.MESES[d.month - 1]}"


ESTADOS = {"APROBADA": ("Aprobada", "ok"), "PENDIENTE": ("En espera", "espera"),
           "PENDIENTE_GERENCIA": ("Espera gerencia", "espera")}
izq, der = st.columns([1.2, 1], gap="medium")
with izq:
    proximas = vac[vac["fin"] >= iso].sort_values("inicio").head(10)
    filas = []
    for r in proximas.itertuples():
        d = date.fromisoformat(max(r.inicio, iso))
        texto, tipo = ESTADOS.get(r.estado, (r.estado, "info"))
        filas.append(f'<li><span class="d-dia"><b>{d.day}</b><small>{estilo.MESES[d.month - 1][:3]}</small></span>'
                     f'<p>{html.escape(estilo.bonito(r.nombre))}<small>Del {fc(r.inicio)} al {fc(r.fin)}, '
                     f'{int(r.dias)} {"día" if r.dias == 1 else "días"}</small></p>{estilo.estado_html(texto, tipo)}</li>')
    cuerpo = ('<ul class="d-lista">' + "".join(filas) + "</ul>") if filas else '<p class="d-vacio">No hay vacaciones programadas.</p>'
    st.markdown(f'<div class="h-panel"><h3>Próximas vacaciones</h3>{cuerpo}</div>', unsafe_allow_html=True)

with der:
    def lista_personas(df, vacio):
        if df.empty:
            return f'<p class="d-vacio">{vacio}</p>'
        nombres = sorted({estilo.bonito(n) for n in df["nombre"]})
        return "".join(f'<p style="margin:4px 0;color:var(--h-tinta)">{html.escape(n)}</p>' for n in nombres)

    st.markdown(f'<div class="h-panel"><h3>Hoy</h3><p style="margin:0 0 4px;color:var(--h-suave)">De vacaciones</p>'
                f'{lista_personas(fuera_hoy, "Nadie está de vacaciones hoy.")}'
                f'<p style="margin:12px 0 4px;color:var(--h-suave)">En teletrabajo</p>'
                f'{lista_personas(tele_hoy, "Nadie tiene teletrabajo hoy.")}</div>', unsafe_allow_html=True)

    # Días de vacaciones (aprobadas y en espera) en los próximos 6 meses
    meses = [(hoy.replace(day=1) + timedelta(days=32 * k)).replace(day=1) for k in range(6)]
    datos = []
    for m in meses:
        fin_m = (m + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        dias = 0
        for r in vac.itertuples():
            a, b = max(date.fromisoformat(r.inicio), m), min(date.fromisoformat(r.fin), fin_m)
            dias += max((b - a).days + 1, 0)
        datos.append({"Mes": f"{estilo.MESES[m.month - 1][:3].capitalize()} {m.year % 100}", "Días": dias})
    with st.container(border=True, key="d_grafico"):
        st.markdown("**Días de vacaciones por mes**")
        st.bar_chart(pd.DataFrame(datos), x="Mes", y="Días", color="#0B4F9C", height=200, sort=False)
