import io

import pandas as pd
import streamlit as st

import db
import seguridad as seg

st.title("Perfiles")

sesion = st.session_state.get("sesion", {})
if sesion.get("rol") != "admin":
    st.error("Solo el administrador puede ver esta página.")
    st.stop()


def respaldo_excel():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for t in db.TABLAS:
            db.consultar(f"SELECT * FROM {t}").to_excel(w, sheet_name=t[:31], index=False)
    return buf.getvalue()


st.download_button(
    "Descargar respaldo (Excel)",
    data=respaldo_excel(),
    file_name=f"respaldo_hermes_{db.hoy():%Y-%m-%d}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="Copia de todas las tablas. Guárdala en un lugar seguro.",
)

usuarios = db.consultar(
    "SELECT usuario, nombre, apellido, rol, cod, estado FROM usuarios ORDER BY estado DESC, usuario"
)
personal = db.consultar("SELECT cod, nombre, puesto FROM rrhh_personal ORDER BY nombre")

ROLES = ["colaborador", "jefe", "admin"]
opciones = {"(sin asociar)": None}
for r in personal.itertuples():
    opciones[f"{r.nombre} ({r.cod}) · {r.puesto}"] = r.cod
valores = list(opciones.values())


def indice(cod):
    return valores.index(cod) if cod in valores else 0


# ---------- Pendientes ----------
pend = usuarios[usuarios["estado"] == "PENDIENTE"]
st.subheader(f"Pendientes de aprobación ({len(pend)})")
if pend.empty:
    st.info("No hay solicitudes pendientes.")
for u in pend.itertuples():
    with st.container(border=True):
        st.markdown(f"**{u.nombre} {u.apellido}** · {u.usuario}")
        c1, c2, c3, c4 = st.columns([4, 2, 1, 1])
        persona = c1.selectbox("Persona en RRHH", list(opciones.keys()), index=indice(u.cod), key=f"p_{u.usuario}")
        rol = c2.selectbox("Rol", ROLES, key=f"r_{u.usuario}")
        if c3.button("Aprobar", key=f"a_{u.usuario}"):
            try:
                seg.actualizar_usuario(u.usuario, rol, opciones[persona], "ACTIVO")
                st.rerun()
            except db.IntegrityError:
                st.error("Esa persona ya está asociada a otro usuario.")
        if c4.button("Rechazar", key=f"x_{u.usuario}"):
            seg.eliminar_usuario(u.usuario)
            st.rerun()

# ---------- Activos ----------
activos = usuarios[usuarios["estado"] == "ACTIVO"]
st.subheader(f"Usuarios activos ({len(activos)})")
st.dataframe(activos, width="stretch", hide_index=True)

if not activos.empty:
    st.markdown("**Editar usuario**")
    sel = st.selectbox("Usuario", activos["usuario"].tolist())
    u = activos[activos["usuario"] == sel].iloc[0]
    c1, c2 = st.columns(2)
    persona = c1.selectbox("Persona en RRHH", list(opciones.keys()), index=indice(u["cod"]), key=f"ep_{sel}")
    rol = c2.selectbox("Rol", ROLES, index=ROLES.index(u["rol"]) if u["rol"] in ROLES else 0, key=f"er_{sel}")

    if st.button("Guardar cambios"):
        if sel == sesion.get("usuario") and rol != "admin":
            st.error("No puedes quitarte a ti mismo el rol de admin.")
        else:
            try:
                seg.actualizar_usuario(sel, rol, opciones[persona], "ACTIVO")
                st.success("Cambios guardados.")
            except db.IntegrityError:
                st.error("Esa persona ya está asociada a otro usuario.")

    nueva = st.text_input("Nueva contraseña (mínimo 6 caracteres)", type="password", key=f"pw_{sel}")
    if st.button("Cambiar contraseña"):
        if len(nueva) < 6:
            st.error("Mínimo 6 caracteres.")
        else:
            seg.cambiar_clave(sel, nueva)
            st.success("Contraseña cambiada.")

    if st.button("Eliminar usuario"):
        if sel == sesion.get("usuario"):
            st.error("No puedes eliminar tu propio usuario.")
        else:
            seg.eliminar_usuario(sel)
            st.rerun()
