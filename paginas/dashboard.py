import streamlit as st

import db

st.title("Dashboard")

sesion = st.session_state.get("sesion", {})
rol = sesion.get("rol")
mi_cod = sesion.get("cod")
hoy = db.hoy().isoformat()
mes = hoy[:7]

vac = db.consultar(
    """SELECT s.cod, p.nombre, p.area, s.inicio, s.fin, s.dias, s.bloque, s.estado
       FROM vacaciones_solicitudes s JOIN rrhh_personal p ON p.cod = s.cod"""
)
tele = db.consultar("SELECT cod, fecha, estado FROM teletrabajo_solicitudes")

pendientes = vac["estado"].isin(["PENDIENTE", "PENDIENTE_GERENCIA"])
tele_mes = tele["fecha"].str.startswith(mes, na=False) & (tele["estado"] != "RECHAZADO")
proximas = vac[(vac["fin"] >= hoy) & (vac["estado"] != "RECHAZADA")].sort_values("inicio")

if rol == "colaborador":
    mias = vac["cod"] == mi_cod
    c1, c2, c3 = st.columns(3)
    c1.metric("Mis solicitudes pendientes", int((mias & pendientes).sum()))
    c2.metric("Mis vacaciones aprobadas", int((mias & (vac["estado"] == "APROBADA")).sum()))
    c3.metric("Mi teletrabajo este mes", int(((tele["cod"] == mi_cod) & tele_mes).sum()))

    st.divider()
    st.subheader("Mis próximas vacaciones")
    st.dataframe(
        proximas[proximas["cod"] == mi_cod][["inicio", "fin", "dias", "bloque", "estado"]],
        width="stretch", hide_index=True,
    )
else:
    total = db.uno("SELECT COUNT(*) AS n FROM rrhh_personal").n
    de_vacaciones = (vac["estado"] == "APROBADA") & (vac["inicio"] <= hoy) & (vac["fin"] >= hoy)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personal registrado", int(total))
    c2.metric("Vacaciones pendientes", int(pendientes.sum()))
    c3.metric("De vacaciones hoy", int(de_vacaciones.sum()))
    c4.metric("Teletrabajo del mes", int(tele_mes.sum()))

    st.divider()
    st.subheader("Próximas vacaciones")
    st.dataframe(
        proximas[["nombre", "area", "inicio", "fin", "dias", "estado"]].head(15),
        width="stretch", hide_index=True,
    )
