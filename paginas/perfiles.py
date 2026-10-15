import io

import pandas as pd
import streamlit as st

import html

import db
import estilo
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
            # los documentos de las facturas no caben en un Excel: solo se listan
            sql = "SELECT id, factura_id, nombre, tipo FROM facturas_archivos" if t == "facturas_archivos" \
                else f"SELECT * FROM {t}"
            db.consultar(sql).to_excel(w, sheet_name=t[:31], index=False)
    return buf.getvalue()


usuarios = db.consultar(
    "SELECT usuario, nombre, apellido, rol, cod, estado FROM usuarios ORDER BY estado DESC, usuario"
)
personal = db.consultar("SELECT cod, nombre, puesto FROM rrhh_personal ORDER BY nombre")
nombre_de = dict(zip(personal["cod"], personal["nombre"]))

ROLES = ["colaborador", "jefe", "admin", "aprobador_facturas"]
NOMBRE_ROL = {"colaborador": "Colaborador", "jefe": "Jefe", "admin": "Administrador",
              "aprobador_facturas": "Aprobador de facturas"}
opciones = {"(sin asociar)": None}
for r in personal.itertuples():
    opciones[f"{estilo.bonito(r.nombre)} ({estilo.bonito(r.puesto)}, {r.cod})"] = r.cod
valores = list(opciones.values())


def indice(cod):
    return valores.index(cod) if cod in valores else 0


def nombre_usuario(u):
    n = " ".join(x for x in (u.get("nombre"), u.get("apellido")) if isinstance(x, str) and x)
    return n or (estilo.bonito(nombre_de[u["cod"]]) if u.get("cod") in nombre_de else u["usuario"])


pend = usuarios[usuarios["estado"] == "PENDIENTE"]
activos = usuarios[usuarios["estado"] == "ACTIVO"].reset_index(drop=True)
st.markdown(f'<div class="h-sub">{len(activos)} {"usuario activo" if len(activos) == 1 else "usuarios activos"}'
            + (f" y {len(pend)} {'solicitud' if len(pend) == 1 else 'solicitudes'} por aprobar." if len(pend) else ".")
            + "</div>", unsafe_allow_html=True)

a1, a2, _ = st.columns([1.3, 1.6, 2.5])
if a1.button("Crear un usuario", icon=":material/person_add:", use_container_width=True):
    st.session_state["pf_crear"] = not st.session_state.get("pf_crear", False)
a2.download_button("Descargar respaldo", data=respaldo_excel(), icon=":material/download:",
                   file_name=f"respaldo_hermes_{db.hoy():%Y-%m-%d}.xlsx", use_container_width=True,
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   help="Copia de todas las tablas. Guárdala en un lugar seguro.")

# ---------- Crear usuario ----------
if st.session_state.get("pf_crear"):
    with st.container(border=True, key="pf_form"):
        st.markdown("**Crear un usuario**")
        st.caption("Para alguien que no se registró por su cuenta, como el aprobador de facturas. "
                   "Queda activo de inmediato; pásale su usuario y contraseña, y pídele que la cambie.")
        with st.form("crear_usuario", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            nuevo_nombre = c1.text_input("Nombre")
            nuevo_apellido = c2.text_input("Apellido")
            c3, c4 = st.columns(2)
            nuevo_usuario = c3.text_input("Correo o usuario")
            nuevo_rol = c4.multiselect("Roles", ROLES, default=["aprobador_facturas"], format_func=NOMBRE_ROL.get,
                                       help="Puedes marcar más de uno")
            c5, c6 = st.columns(2)
            clave1 = c5.text_input("Contraseña (mínimo 6 caracteres)", type="password")
            clave2 = c6.text_input("Repite la contraseña", type="password")
            if st.form_submit_button("Crear usuario", type="primary"):
                if not nuevo_usuario.strip() or not nuevo_nombre.strip():
                    st.error("Completa nombre y correo o usuario.")
                elif not nuevo_rol:
                    st.error("Elige al menos un rol.")
                elif len(clave1) < 6 or clave1 != clave2:
                    st.error("La contraseña debe tener al menos 6 caracteres y coincidir en ambos campos.")
                else:
                    try:
                        seg.crear_usuario(nuevo_usuario, clave1, nuevo_rol, None, nuevo_nombre.strip(),
                                          nuevo_apellido.strip() or None, "ACTIVO")
                        st.success(f"Usuario {nuevo_usuario.strip().lower()} creado como "
                                   f"{' y '.join(NOMBRE_ROL[r].lower() for r in nuevo_rol)}.")
                    except db.IntegrityError:
                        st.error("Ese correo o usuario ya existe.")

# ---------- Pendientes ----------
if not pend.empty:
    st.markdown('<div class="a-cab" style="margin-top:10px"><b>Por aprobar</b>'
                '<span>Personas que crearon su usuario y esperan tu aprobación</span></div>', unsafe_allow_html=True)
for u in pend.to_dict("records"):
    with st.container(border=True, key=f"pf_pend_{u['usuario']}"):
        nom = nombre_usuario(u)
        sugerida = f"Coincide con {estilo.bonito(nombre_de[u['cod']])} en el personal." if u["cod"] in nombre_de \
            else "No se encontró automáticamente en el personal: elige a la persona."
        st.markdown(f'<div class="pf-quien"><span class="h-iniciales">{html.escape(estilo.iniciales(nom))}</span>'
                    f'<div><b>{html.escape(nom)}</b><small>{html.escape(u["usuario"])}. {html.escape(sugerida)}</small></div></div>',
                    unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([3.2, 1.6, 1, 1], vertical_alignment="bottom")
        persona = c1.selectbox("Persona en el personal", list(opciones.keys()), index=indice(u["cod"]), key=f"p_{u['usuario']}")
        rol = c2.multiselect("Roles", ROLES, default=["colaborador"], key=f"r_{u['usuario']}", format_func=NOMBRE_ROL.get)
        if c3.button("Aprobar", key=f"a_{u['usuario']}", type="primary", use_container_width=True):
            if not rol:
                st.error("Elige al menos un rol.")
                st.stop()
            try:
                seg.actualizar_usuario(u["usuario"], rol, opciones[persona], "ACTIVO")
                st.rerun()
            except db.IntegrityError:
                st.error("Esa persona ya está asociada a otro usuario.")
        if c4.button("Rechazar", key=f"x_{u['usuario']}", use_container_width=True):
            seg.eliminar_usuario(u["usuario"])
            st.rerun()

# ---------- Activos: lista y ficha ----------
st.markdown('<div class="a-cab" style="margin-top:14px"><b>Usuarios activos</b>'
            '<span>Elige uno para editarlo</span></div>', unsafe_allow_html=True)
izq, der = st.columns([1.4, 1], gap="medium")
with izq:
    tabla = pd.DataFrame({
        "Nombre": [nombre_usuario(u) for u in activos.to_dict("records")],
        "Usuario": activos["usuario"],
        "Roles": activos["rol"].map(lambda r: ", ".join(NOMBRE_ROL.get(x, x) for x in seg.roles_de(r))),
        "Persona en el personal": activos["cod"].map(lambda c: estilo.bonito(nombre_de[c]) if c in nombre_de else "Sin asociar"),
    })
    ev = st.dataframe(tabla, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                      key="pf_lista", height=min(38 + 35 * max(len(tabla), 1), 520))
    filas = ev.selection.rows
with der:
    if not filas:
        st.markdown('<div class="h-panel" style="color:var(--h-suave);text-align:center;padding:36px 12px">'
                    'Elige un usuario de la lista para cambiar su rol, la persona asociada o su contraseña.</div>',
                    unsafe_allow_html=True)
    else:
        u = activos.iloc[filas[0]].to_dict()
        sel = u["usuario"]
        with st.container(border=True, key="pf_ficha"):
            nom = nombre_usuario(u)
            st.markdown(f'<div class="pf-quien"><span class="h-iniciales">{html.escape(estilo.iniciales(nom))}</span>'
                        f'<div><b>{html.escape(nom)}</b><small>{html.escape(sel)}</small></div></div>', unsafe_allow_html=True)
            persona = st.selectbox("Persona en el personal", list(opciones.keys()), index=indice(u["cod"]), key=f"ep_{sel}")
            rol = st.multiselect("Roles", ROLES, default=seg.roles_de(u["rol"]), key=f"er_{sel}",
                                 format_func=NOMBRE_ROL.get, help="Puedes marcar más de uno")
            if st.button("Guardar cambios", type="primary", use_container_width=True, key=f"eg_{sel}"):
                if not rol:
                    st.error("Elige al menos un rol.")
                elif sel == sesion.get("usuario") and "admin" not in rol:
                    st.error("No puedes quitarte a ti mismo el rol de administrador.")
                else:
                    try:
                        seg.actualizar_usuario(sel, rol, opciones[persona], "ACTIVO")
                        st.success("Cambios guardados.")
                    except db.IntegrityError:
                        st.error("Esa persona ya está asociada a otro usuario.")
            st.divider()
            nueva = st.text_input("Nueva contraseña (mínimo 6 caracteres)", type="password", key=f"pw_{sel}")
            if st.button("Cambiar contraseña", use_container_width=True, key=f"pwb_{sel}"):
                if len(nueva) < 6:
                    st.error("Mínimo 6 caracteres.")
                else:
                    seg.cambiar_clave(sel, nueva)
                    st.success("Contraseña cambiada.")
            if st.button("Eliminar usuario", type="tertiary", key=f"del_{sel}"):
                if sel == sesion.get("usuario"):
                    st.error("No puedes eliminar tu propio usuario.")
                else:
                    seg.eliminar_usuario(sel)
                    st.rerun()

st.markdown("""<style>
.pf-quien { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
.pf-quien b { display: block; color: var(--h-tinta); }
.pf-quien small { color: var(--h-suave); }
.a-cab { display: flex; justify-content: space-between; align-items: baseline; margin: 6px 0 10px; }
.a-cab b { font-size: 1.05rem; color: var(--h-tinta); }
.a-cab span { color: var(--h-suave); font-size: 0.9rem; }
[class*="st-key-pf_"] { background: var(--h-superficie); }
</style>""", unsafe_allow_html=True)
