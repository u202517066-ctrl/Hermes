import streamlit as st

import html
from pathlib import Path

import db
import estilo
import seguridad as seg
from reglas_vacaciones import jefes_por_area

CARPETA = Path(__file__).resolve().parent
st.set_page_config(page_title="HERMES", page_icon="🛡️", layout="wide")
estilo.aplicar()


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


RUTA_SVG = """<svg viewBox="0 0 600 320" preserveAspectRatio="none" aria-hidden="true" class="h-ruta">
<path d="M-10 250 C 120 250, 150 140, 280 150 S 470 260, 610 90" fill="none" stroke="rgba(255,255,255,0.18)"
 stroke-width="34" stroke-linecap="round"/>
<path d="M-10 250 C 120 250, 150 140, 280 150 S 470 260, 610 90" fill="none" stroke="rgba(255,255,255,0.55)"
 stroke-width="2" stroke-dasharray="14 12"/>
<circle cx="280" cy="150" r="9" fill="#E9A23B"/>
<circle cx="280" cy="150" r="18" fill="none" stroke="#E9A23B" stroke-opacity="0.45" stroke-width="2"/></svg>"""

CSS_ACCESO = """<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 3rem; max-width: 1080px; }
div[data-testid="stForm"] { background: transparent !important; border: 0 !important; padding: 0 !important; }
.st-key-acceso { background: var(--h-superficie); border: 1px solid var(--h-linea); border-radius: 18px; overflow: hidden; }
.st-key-acceso > div > [data-testid="stHorizontalBlock"] { gap: 0 !important; }
.st-key-acceso_form { padding: 6px 44px 30px; }
.st-key-acceso .h-acceso-marca { border-radius: 0; min-height: 620px; }
.stApp .h-acceso-titulo { font-size: 1.8rem; }
.h-acceso-marca { background: #083A75; color: #FFFFFF; border-radius: 18px; padding: 40px; min-height: 520px;
  position: relative; overflow: hidden; display: flex; flex-direction: column; }
.h-acceso-marca .logo { font-stretch: 75%; font-weight: 800; font-size: 3.2rem; letter-spacing: 0.03em; line-height: 1; }
.h-acceso-marca p { font-size: 1.12rem; max-width: 30ch; margin: 16px 0 0; opacity: 0.92; color: #FFFFFF; }
.h-acceso-marca footer { margin-top: auto; position: relative; font-size: 0.85rem; opacity: 0.75; }
.h-ruta { position: absolute; left: 0; right: 0; bottom: 0; width: 100%; height: 52%; }
.h-acceso-titulo { font-size: 1.7rem; font-weight: 700; margin: 3.2rem 0 0.2rem; color: var(--h-tinta); }
.h-acceso-sub { color: var(--h-suave); margin-bottom: 1.2rem; }
@media (max-width: 760px) { .st-key-acceso .h-acceso-marca { min-height: 220px; } .h-acceso-titulo { margin-top: 0.5rem; }
  .st-key-acceso_form { padding: 6px 20px 24px; } }
</style>"""


def pantalla_acceso():
    st.markdown(CSS_ACCESO, unsafe_allow_html=True)
    tarjeta = st.container(key="acceso")
    izq, der = tarjeta.columns([1.05, 1], gap="small")
    with izq:
        st.markdown(
            f"""<div class="h-acceso-marca"><div class="logo">HERMES</div>
<p>Vacaciones, teletrabajo y aprobaciones del equipo comercial, en un solo lugar.</p>
{RUTA_SVG}<footer>Hermes Transportes Blindados</footer></div>""",
            unsafe_allow_html=True,
        )
    with der, st.container(key="acceso_form"):
        if st.session_state.get("acceso_modo") != "registro":
            st.markdown('<div class="h-acceso-titulo">Ingresa a tu cuenta</div>'
                        '<div class="h-acceso-sub">Usa el correo con el que te registraste.</div>',
                        unsafe_allow_html=True)
            # Dentro de un formulario, Enter en cualquier campo equivale a presionar «Ingresar»
            with st.form("login", border=False):
                u = st.text_input("Correo o usuario", key="login_u", placeholder="nombre@hermes.com.pe")
                c = st.text_input("Contraseña", type="password", key="login_c")
                entrar = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            st.caption("También puedes presionar Enter para ingresar.")
            if entrar:
                datos = seg.verificar(u, c)
                if datos and "error" in datos:
                    st.warning(datos["error"])
                elif datos:
                    st.session_state["sesion"] = datos
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            st.divider()
            st.markdown("¿Primera vez en HERMES?")
            if st.button("Crear mi usuario", type="tertiary"):
                st.session_state["acceso_modo"] = "registro"
                st.rerun()
        else:
            st.markdown('<div class="h-acceso-titulo">Crea tu usuario</div>'
                        '<div class="h-acceso-sub">El administrador aprobará tu cuenta antes de que puedas ingresar.</div>',
                        unsafe_allow_html=True)
            with st.form("registro", border=False):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre", key="r_nombre")
                apellido = c2.text_input("Apellido", key="r_apellido")
                correo = st.text_input("Correo", key="r_correo", placeholder="nombre@hermes.com.pe")
                c3, c4 = st.columns(2)
                k1 = c3.text_input("Contraseña", type="password", key="r_c1", help="Mínimo 6 caracteres")
                k2 = c4.text_input("Repite la contraseña", type="password", key="r_c2")
                crear = st.form_submit_button("Crear mi usuario", type="primary", use_container_width=True)
            if crear:
                if len(k1) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                elif k1 != k2:
                    st.error("Las contraseñas no coinciden.")
                else:
                    error = seg.registrar(nombre, apellido, correo, k1)
                    if error:
                        st.error(error)
                    else:
                        st.success("Solicitud enviada. Podrás ingresar cuando el administrador apruebe tu cuenta.")
            if st.button("Ya tengo usuario: ingresar", type="tertiary"):
                st.session_state["acceso_modo"] = "ingreso"
                st.rerun()


sesion = st.session_state.get("sesion")
if not sesion:
    # La pantalla de ingreso se muestra como única página y sin menú, para que no quede
    # a la vista el menú de la sesión anterior al cerrar sesión.
    st.navigation([st.Page(pantalla_acceso, title="Ingresar", url_path="ingresar", default=True)],
                  position="hidden").run()
    st.stop()

# Refresca rol y persona asociada en cada carga (por si el admin los cambió o eliminó la cuenta)
actual = seg.datos_usuario(sesion["usuario"])
if not actual or actual["estado"] != "ACTIVO":
    st.session_state.pop("sesion", None)
    st.rerun()
roles = seg.roles_de(actual["rol"])
# Los jefes de área (reglas_vacaciones.APROBADORES) entran como jefes aunque en Perfiles figuren como colaborador
if "jefe" not in roles and "admin" not in roles and actual["cod"]:
    if actual["cod"] in jefes_por_area(db.consultar("SELECT cod, nombre, area FROM rrhh_personal")).values():
        roles.append("jefe")
# "rol" es el rol principal (lo usan las pantallas); "roles" son todos los que tiene
sesion.update(rol=seg.rol_principal(roles), roles=roles, cod=actual["cod"])

rol = sesion["rol"]
es_jefatura = rol in ("jefe", "admin")
aprueba_facturas = "aprobador_facturas" in roles

NOMBRE_ROL = {"colaborador": "Colaborador", "jefe": "Jefe", "admin": "Administrador",
              "aprobador_facturas": "Aprobador de facturas"}
ficha = db.uno("SELECT nombre, puesto FROM rrhh_personal WHERE cod = :c", {"c": sesion["cod"]}) if sesion["cod"] else None
nombre_mostrar = (estilo.bonito(ficha.nombre) if ficha else
                  " ".join(x for x in (actual.get("nombre"), actual.get("apellido")) if x) or sesion["usuario"])
sesion["nombre"] = nombre_mostrar
detalle = estilo.bonito(ficha.puesto) if ficha and ficha.puesto else " y ".join(NOMBRE_ROL.get(r, r) for r in roles)

# Logo del menú: si falta la carpeta assets, la app sigue funcionando sin él
logo, icono = CARPETA / "assets" / "logo.svg", CARPETA / "assets" / "icono.svg"
if logo.exists():
    st.logo(str(logo), size="large", icon_image=str(icono) if icono.exists() else None)


def pie_menu():
    estilo.tarjeta_usuario(nombre_mostrar, detalle)
    if st.sidebar.button("Cerrar sesión", icon=":material/logout:", type="tertiary"):
        st.session_state.pop("sesion", None)
        st.rerun()


if rol == "aprobador_facturas":  # solo es aprobador de facturas: ve únicamente Facturas
    pie_menu()
    st.navigation({"Finanzas": [st.Page("paginas/facturas.py", title="Facturas", icon=":material/receipt_long:",
                                        default=True)]}).run()
    st.stop()

# Pantalla que se abre al entrar: Aprobaciones para jefes y administrador; Vacaciones para colaboradores
menu = {}
if es_jefatura:
    menu["Mi equipo"] = [
        st.Page("paginas/aprobaciones.py", title="Aprobaciones", icon=":material/task_alt:", default=True),
        st.Page("paginas/dashboard.py", title="Indicadores", icon=":material/insights:"),
        st.Page("paginas/directorio.py", title="Directorio", icon=":material/groups:"),
    ]
menu["Mi trabajo"] = [
    st.Page("paginas/vacaciones.py", title="Vacaciones", icon=":material/beach_access:", default=not es_jefatura),
    st.Page("paginas/teletrabajo.py", title="Teletrabajo", icon=":material/home_work:"),
]
if rol == "admin" or aprueba_facturas:
    menu["Finanzas"] = [st.Page("paginas/facturas.py", title="Facturas", icon=":material/receipt_long:")]
if rol == "admin":
    menu["Administración"] = [st.Page("paginas/perfiles.py", title="Perfiles", icon=":material/manage_accounts:")]

pie_menu()
pg = st.navigation(menu)
pg.run()
