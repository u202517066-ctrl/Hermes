import streamlit as st

import db
import seguridad as seg
from reglas_vacaciones import jefes_por_area

st.set_page_config(page_title="HERMES", layout="wide")


@st.cache_resource
def iniciar_bd(tablas):
    # Se vuelve a ejecutar sola cuando db.py agrega tablas nuevas
    db.crear_tablas()
    return True


try:
    iniciar_bd(tuple(db.TABLAS) + (db.VERSION_ESQUEMA,))
except Exception as e:
    st.error("No se pudo conectar a la base de datos. Revisa DB_URL en los secrets.")
    st.caption(f"{type(e).__name__}: {str(e)[:300]}")
    st.stop()


def pantalla_acceso():
    st.title("HERMES")
    tab1, tab2 = st.tabs(["Ingresar", "Crear mi usuario"])

    with tab1:
        u = st.text_input("Correo o usuario", key="login_u")
        c = st.text_input("Contraseña", type="password", key="login_c")
        if st.button("Ingresar", type="primary"):
            datos = seg.verificar(u, c)
            if datos and "error" in datos:
                st.warning(datos["error"])
            elif datos:
                st.session_state["sesion"] = datos
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

    with tab2:
        nombre = st.text_input("Nombre", key="r_nombre")
        apellido = st.text_input("Apellido", key="r_apellido")
        correo = st.text_input("Correo", key="r_correo")
        c1 = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="r_c1")
        c2 = st.text_input("Repite la contraseña", type="password", key="r_c2")
        if st.button("Crear mi usuario"):
            if len(c1) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif c1 != c2:
                st.error("Las contraseñas no coinciden.")
            else:
                error = seg.registrar(nombre, apellido, correo, c1)
                if error:
                    st.error(error)
                else:
                    st.success("Solicitud enviada. Podrás ingresar cuando el administrador apruebe tu cuenta.")


sesion = st.session_state.get("sesion")
if not sesion:
    pantalla_acceso()
    st.stop()

# Refresca rol y persona asociada en cada carga (por si el admin los cambió o eliminó la cuenta)
actual = seg.datos_usuario(sesion["usuario"])
if not actual or actual["estado"] != "ACTIVO":
    st.session_state.pop("sesion", None)
    st.rerun()
sesion.update(rol=actual["rol"], cod=actual["cod"])
# Los jefes de área (reglas_vacaciones.APROBADORES) entran como jefes aunque en Perfiles figuren como colaborador
if sesion["rol"] == "colaborador" and sesion["cod"]:
    if sesion["cod"] in jefes_por_area(db.consultar("SELECT cod, nombre, area FROM rrhh_personal")).values():
        sesion["rol"] = "jefe"

rol = sesion["rol"]
es_jefatura = rol in ("jefe", "admin")

if rol == "aprobador_facturas":  # solo ve las facturas por aprobar
    st.sidebar.title("HERMES")
    st.sidebar.caption(f"{sesion['usuario']} · aprobador de facturas")
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.pop("sesion", None)
        st.rerun()
    st.navigation({"FINANZAS": [st.Page("paginas/facturas.py", title="Facturas", default=True)]}).run()
    st.stop()

menu = {
    "PRINCIPAL": [st.Page("paginas/dashboard.py", title="Dashboard", default=True)],
    "GESTIÓN LABORAL": [
        st.Page("paginas/vacaciones.py", title="Vacaciones"),
        st.Page("paginas/teletrabajo.py", title="Teletrabajo"),
    ]
    + ([st.Page("paginas/aprobaciones.py", title="Aprobaciones")] if es_jefatura else []),
}
if rol == "admin":
    menu["FINANZAS"] = [st.Page("paginas/facturas.py", title="Facturas")]
if es_jefatura:
    administracion = [st.Page("paginas/directorio.py", title="Directorio")]
    if rol == "admin":
        administracion.append(st.Page("paginas/perfiles.py", title="Perfiles"))
    menu["ADMINISTRACIÓN"] = administracion

st.sidebar.title("HERMES")
st.sidebar.caption(f"{sesion['usuario']} · {rol}")
if st.sidebar.button("Cerrar sesión"):
    st.session_state.pop("sesion", None)
    st.rerun()

pg = st.navigation(menu)
pg.run()
