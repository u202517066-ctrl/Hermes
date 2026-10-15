import html
from datetime import date, datetime, timedelta

import streamlit as st

import db
import estilo
from reglas_vacaciones import DIAS_PERIODO, MESES_CICLO, inicio_ciclo, jefes_por_area, primer_aniversario, sumar_meses

st.markdown(
    """
<style>
.stApp .i-saludo { font-stretch: 75%; font-weight: 800; font-size: 2.4rem; line-height: 1.1; color: var(--h-tinta); margin: 0; }
.i-saldo { background: var(--h-azul); color: #FFFFFF; border-radius: 18px; padding: 22px 26px;
  display: grid; grid-template-columns: auto 1fr; gap: 10px 32px; align-items: end; margin-bottom: 6px; }
.i-cifra { font-stretch: 75%; font-weight: 800; font-size: 4.4rem; line-height: 0.9; }
.i-cifra small { display: block; font-stretch: 100%; font-size: 0.95rem; font-weight: 500; opacity: 0.88; margin-top: 8px; }
.i-tramo { display: grid; grid-template-columns: repeat(30, 1fr); gap: 3px; }
.i-tramo i { height: 26px; border-radius: 4px; background: rgba(255,255,255,0.18); }
.i-tramo i.t { background: #FFFFFF; }
.i-tramo i.e { background: repeating-linear-gradient(135deg, #FFFFFF 0 3px, rgba(255,255,255,0.35) 3px 6px); }
.i-ley { display: flex; gap: 18px; flex-wrap: wrap; font-size: 0.85rem; margin-top: 8px; opacity: 0.92; }
.i-ley span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.i-ley .t::before { background: #FFFFFF; }
.i-ley .e::before { background: repeating-linear-gradient(135deg, #FFFFFF 0 2px, rgba(255,255,255,0.35) 2px 4px); }
.i-ley .l::before { background: rgba(255,255,255,0.28); }
.i-nota { grid-column: 1 / -1; margin: 4px 0 0; opacity: 0.92; }
.i-semana { width: 100%; border-collapse: separate; border-spacing: 4px; table-layout: fixed; }
.i-semana th { font-size: 0.8rem; color: var(--h-suave); font-weight: 600; text-align: center; }
.i-semana th:first-child { width: 36%; text-align: left; }
.i-semana th.hoy { color: var(--h-azul); }
.i-semana, .i-semana thead, .i-semana tbody, .i-semana tr, .i-semana th, .i-semana td { border: 0 !important; box-shadow: none !important; }
.i-semana tr { background: transparent !important; }
.i-semana td { height: 32px; border-radius: 8px; background: var(--h-fondo); font-size: 0.75rem; text-align: center; font-weight: 600; }
.i-semana td:first-child { background: none; text-align: left; font-weight: 500; font-size: 0.86rem;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--h-tinta); }
.i-semana td.vac { background: var(--h-azul); color: #FFFFFF; }
.i-semana td.vacp { background: repeating-linear-gradient(135deg, var(--h-celeste) 0 5px, var(--h-superficie) 5px 10px); color: var(--h-azul); }
.i-semana td.tele { background: var(--h-celeste); color: var(--h-azul); }
.i-semana td.fer { background: repeating-linear-gradient(135deg, var(--h-rojo-suave) 0 5px, transparent 5px 10px); color: var(--h-rojo); }
.i-lista { list-style: none; margin: 0; padding: 0; }
.i-lista li { display: grid; grid-template-columns: 50px 1fr auto; gap: 12px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--h-linea); }
.i-lista li:last-child { border-bottom: 0; }
.i-dia { text-align: center; border-radius: 10px; background: var(--h-fondo); padding: 4px 0; line-height: 1.1; color: var(--h-tinta); }
.i-dia b { display: block; font-size: 1.25rem; font-stretch: 75%; }
.i-dia small { font-size: 0.72rem; color: var(--h-suave); }
.i-lista p { margin: 0; font-weight: 600; color: var(--h-tinta); }
.i-lista p small { display: block; font-weight: 400; color: var(--h-suave); }
.i-ley2 { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.8rem; color: var(--h-suave); margin-top: 8px; }
.i-tarea { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--h-linea); }
@media (max-width: 760px) { .i-saldo { grid-template-columns: 1fr; } }
</style>
""",
    unsafe_allow_html=True,
)

sesion = st.session_state.get("sesion", {})
rol, mi_cod = sesion.get("rol"), sesion.get("cod")
hoy = db.hoy()
ahora = datetime.now(db.ZONA)
saludo = "Buenos días" if ahora.hour < 12 else "Buenas tardes" if ahora.hour < 19 else "Buenas noches"

ficha = db.uno("SELECT * FROM rrhh_personal WHERE cod = :c", {"c": mi_cod}) if mi_cod else None
if ficha:
    nombre = estilo.nombre_pila(ficha.nombre)
else:  # sin ficha de personal: se usa el nombre registrado en el usuario, si lo hay
    u = db.uno("SELECT nombre FROM usuarios WHERE usuario = :u", {"u": sesion.get("usuario")})
    nombre = (u.nombre or "").split(" ")[0].title() if u and u.nombre else ""
st.markdown(f'<div class="i-saludo">{saludo}{", " + html.escape(nombre) if nombre else ""}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="h-sub" style="margin-top:4px">{estilo.fecha_larga(hoy)}</div>', unsafe_allow_html=True)


def fc(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} de {estilo.MESES[d.month - 1]}"


# ---------- Tareas del administrador ----------
if rol == "admin":
    vac_pend = db.uno("SELECT COUNT(*) AS n FROM vacaciones_solicitudes WHERE estado LIKE 'PENDIENTE%'").n
    tele_pend = db.uno("SELECT COUNT(*) AS n FROM teletrabajo_solicitudes WHERE estado = 'PENDIENTE'").n
    usu_pend = db.uno("SELECT COUNT(*) AS n FROM usuarios WHERE estado = 'PENDIENTE'").n
    fac = db.consultar("SELECT estado, fecha_vencimiento FROM facturas_proveedores "
                       "WHERE estado IN ('PENDIENTE', 'APROBADA', 'OBSERVADA')")
    fac_venc = int((fac["fecha_vencimiento"].fillna("9999") < hoy.isoformat()).sum()) if not fac.empty else 0
    tareas = [
        (vac_pend + tele_pend, ("solicitud de vacaciones o teletrabajo en espera",
                                "solicitudes de vacaciones o teletrabajo en espera"), "paginas/aprobaciones.py", "Revisar"),
        (fac_venc, ("factura vencida sin pagar", "facturas vencidas sin pagar"), "paginas/facturas.py", "Ver facturas"),
        (int((fac["estado"] == "PENDIENTE").sum()) if not fac.empty else 0, ("factura por aprobar", "facturas por aprobar"),
         "paginas/facturas.py", "Ver facturas"),
        (usu_pend, ("usuario nuevo por aprobar", "usuarios nuevos por aprobar"), "paginas/perfiles.py", "Ir a Perfiles"),
    ]
    tareas = [t for t in tareas if t[0]]
    with st.container(border=True):
        st.markdown("**Pendientes**")
        if not tareas:
            st.caption("No tienes nada pendiente.")
        for i, (n, texto, pagina, boton) in enumerate(tareas):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{n}** {texto[0] if n == 1 else texto[1]}")
            c2.page_link(pagina, label=boton, icon=":material/arrow_forward:")

if not ficha:
    if rol != "admin":
        st.info("Tu usuario todavía no está asociado a tu ficha de personal. Pide al administrador que lo asocie en Perfiles.")
    st.stop()

# ---------- Saldo de vacaciones ----------
solicitudes = db.consultar("SELECT cod, inicio, fin, dias, estado FROM vacaciones_solicitudes WHERE estado <> 'RECHAZADA'")
mias = solicitudes[solicitudes["cod"] == mi_cod].sort_values("inicio")
try:
    ingreso = date.fromisoformat(str(ficha.f_ingreso))
except ValueError:
    ingreso = None
c_ini = inicio_ciclo(ingreso, hoy) if ingreso else None

if ingreso and c_ini is None:
    st.markdown(f"""<div class="i-saldo"><div class="i-cifra">0<small>días por ahora</small></div>
<div>Podrás programar tus vacaciones desde el {primer_aniversario(ingreso):%d/%m/%Y}, cuando cumplas 1 año en la empresa.</div></div>""",
                unsafe_allow_html=True)
elif c_ini:
    fin_ciclo = sumar_meses(c_ini, MESES_CICLO)
    en_ciclo = mias[(mias["inicio"] >= c_ini.isoformat()) & (mias["inicio"] < fin_ciclo.isoformat())]
    tomados = int(en_ciclo[en_ciclo["estado"] == "APROBADA"]["dias"].sum())
    espera = int(en_ciclo[en_ciclo["estado"] != "APROBADA"]["dias"].sum())
    libres = max(DIAS_PERIODO - tomados - espera, 0)
    cuadros = "".join(f'<i class="{c}"></i>' for c in ["t"] * tomados + ["e"] * espera + [""] * libres)
    pendiente = mias[(mias["estado"] != "APROBADA") & (mias["fin"] >= hoy.isoformat())]
    proxima = mias[(mias["estado"] == "APROBADA") & (mias["fin"] >= hoy.isoformat())]
    if not pendiente.empty:
        r = pendiente.iloc[0]
        nota = f"Tu solicitud del {fc(r['inicio'])} al {fc(r['fin'])} está esperando respuesta."
    elif not proxima.empty:
        r = proxima.iloc[0]
        nota = f"Tus próximas vacaciones: del {fc(r['inicio'])} al {fc(r['fin'])}."
    else:
        nota = "Aún no tienes vacaciones programadas en este periodo."
    st.markdown(f"""<div class="i-saldo"><div class="i-cifra">{libres}<small>días por programar</small></div>
<div><div class="i-tramo">{cuadros}</div>
<div class="i-ley"><span class="t">{tomados} tomados</span><span class="e">{espera} en espera</span><span class="l">{libres} disponibles</span></div></div>
<p class="i-nota">{html.escape(nota)}</p></div>""", unsafe_allow_html=True)
    st.page_link("paginas/vacaciones.py", label="Pedir vacaciones", icon=":material/beach_access:")

# ---------- Semana del equipo y lo que viene ----------
personal = db.consultar("SELECT cod, nombre, area, seccion FROM rrhh_personal")
seccion = str(ficha.seccion or "")
if seccion.upper().startswith("GRUPO"):
    equipo, titulo_eq = personal[personal["seccion"] == seccion], f"Tu grupo esta semana ({seccion.replace('_', ' ').title()})"
else:
    areas = [a for a, c in jefes_por_area(personal).items() if c == mi_cod] or [ficha.area]
    equipo, titulo_eq = personal[personal["area"].isin(areas)], "Tu equipo esta semana"
equipo = equipo.sort_values("nombre").head(10)

lunes = hoy - timedelta(days=hoy.weekday()) if hoy.weekday() < 5 else hoy + timedelta(days=7 - hoy.weekday())
dias = [lunes + timedelta(days=k) for k in range(5)]
feriados = db.consultar("SELECT fecha, nombre FROM feriados")
fer = dict(zip(feriados["fecha"], feriados["nombre"]))
tele = db.consultar("SELECT cod, fecha, estado FROM teletrabajo_solicitudes WHERE estado <> 'RECHAZADO'")

col1, col2 = st.columns([1.15, 1], gap="medium")
with col1:
    cab = "".join(f'<th class="{"hoy" if d == hoy else ""}">{estilo.DIAS_CORTOS[d.weekday()]} {d.day}</th>' for d in dias)
    filas = []
    for p in equipo.itertuples():
        celdas = []
        for d in dias:
            iso = d.isoformat()
            v = solicitudes[(solicitudes["cod"] == p.cod) & (solicitudes["inicio"] <= iso) & (solicitudes["fin"] >= iso)]
            if iso in fer:
                celdas.append('<td class="fer">Feriado</td>')
            elif not v.empty:
                celdas.append('<td class="vac">Vac.</td>' if (v["estado"] == "APROBADA").any() else '<td class="vacp">Vac.</td>')
            elif ((tele["cod"] == p.cod) & (tele["fecha"] == iso)).any():
                celdas.append('<td class="tele">Casa</td>')
            else:
                celdas.append("<td></td>")
        filas.append(f"<tr><td>{html.escape(estilo.bonito(p.nombre))}</td>{''.join(celdas)}</tr>")
    st.markdown(f"""<div class="h-panel"><h3>{html.escape(titulo_eq)}</h3>
<table class="i-semana"><thead><tr><th></th>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>
<div class="i-ley2"><span class="h-estado info">Vac. = vacaciones</span><span class="h-estado info">Casa = teletrabajo</span>
<span>Rayado: en espera de aprobación</span></div></div>""", unsafe_allow_html=True)

with col2:
    limite = (hoy + timedelta(days=60)).isoformat()
    eventos = []
    for r in tele[(tele["cod"] == mi_cod) & (tele["fecha"] >= hoy.isoformat()) & (tele["fecha"] <= limite)].itertuples():
        aprobado = r.estado == "APROBADO"
        eventos.append((r.fecha, "Teletrabajo", estilo.DIAS[date.fromisoformat(r.fecha).weekday()].capitalize(),
                        estilo.estado_html("Aprobado" if aprobado else "En espera", "ok" if aprobado else "espera")))
    for f, n in fer.items():
        if hoy.isoformat() <= f <= limite:
            habil = date.fromisoformat(f).weekday() < 5
            eventos.append((f, html.escape(n or "Feriado"),
                            "Esa semana no se programa teletrabajo" if habil else f"Cae {estilo.DIAS[date.fromisoformat(f).weekday()]}",
                            estilo.estado_html("Feriado", "no")))
    for r in mias[(mias["fin"] >= hoy.isoformat()) & (mias["inicio"] <= limite)].itertuples():
        aprobada = r.estado == "APROBADA"
        eventos.append((max(r.inicio, hoy.isoformat()), f"Vacaciones, {int(r.dias)} días", f"Del {fc(r.inicio)} al {fc(r.fin)}",
                        estilo.estado_html("Aprobada" if aprobada else "En espera", "ok" if aprobada else "espera")))
    eventos.sort(key=lambda e: e[0])
    items = "".join(
        f'<li><span class="i-dia"><b>{date.fromisoformat(f).day}</b><small>{estilo.MESES[date.fromisoformat(f).month - 1][:3]}</small></span>'
        f'<p>{t}<small>{html.escape(s)}</small></p>{e}</li>' for f, t, s, e in eventos[:6])
    st.markdown(f"""<div class="h-panel"><h3>Lo que viene</h3>
{'<ul class="i-lista">' + items + '</ul>' if items else '<p style="color:var(--h-suave);margin:0">Nada programado en los próximos 60 días.</p>'}
</div>""", unsafe_allow_html=True)
