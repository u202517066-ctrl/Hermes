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
.a-cab { display: flex; justify-content: space-between; align-items: baseline; margin: 6px 0 10px; gap: 8px; }
.a-cab b { font-size: 1.05rem; color: var(--h-tinta); }
.a-cab span { color: var(--h-suave); font-size: 0.9rem; }
.i-ped { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
.i-ped b { display: block; color: var(--h-tinta); }
.i-ped small { display: block; color: var(--h-suave); margin-bottom: 4px; }
[class*="st-key-inu_"] { border-left: 4px solid var(--h-ambar) !important; }
[class*="st-key-ini"], [class*="st-key-inu_"] { background: var(--h-superficie); }
.i-mini { margin: 8px 0 6px; color: var(--h-suave); font-size: 0.85rem; }
.i-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.i-nadie { color: var(--h-suave); font-size: 0.9rem; }
.i-dc { display: none; }
/* Botones lado a lado también en el celular */
[class*="st-key-ini"] [data-testid="stHorizontalBlock"], [class*="st-key-inu_"] [data-testid="stHorizontalBlock"],
[class*="st-key-iox_"] [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important; gap: 8px !important; align-items: center; }
[class*="st-key-ini"] [data-testid="stColumn"], [class*="st-key-inu_"] [data-testid="stColumn"],
[class*="st-key-iox_"] [data-testid="stColumn"] {
  min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }
[class*="st-key-iox_"] [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; }
@media (max-width: 760px) {
  .i-saldo { grid-template-columns: 1fr; padding: 18px; }
  .i-cifra { font-size: 3.4rem; }
  .i-tramo { gap: 2px; } .i-tramo i { height: 20px; border-radius: 3px; }
  .stApp .i-saludo { font-size: 2rem; }
  .i-semana { border-spacing: 2px; }
  .i-semana th:first-child { width: 38%; }
  .i-semana .i-dl { display: none; } .i-semana .i-dc { display: inline; }
  .i-semana td { height: 30px; font-size: 0.68rem; }
  .i-semana th { white-space: nowrap; font-size: 0.72rem; }
  .i-semana td .i-dl { display: none; } .i-semana td .i-dc { display: inline; }
  .i-semana td:first-child { font-size: 0.8rem; }
}
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


# ---------- Jefes y administrador: lo que hay que resolver hoy ----------
def rango(a, b):
    a, b = date.fromisoformat(a), date.fromisoformat(b)
    if (a.year, a.month) == (b.year, b.month):
        return f"del {a.day} al {b.day} de {estilo.MESES[b.month - 1]}"
    return f"del {a.day} de {estilo.MESES[a.month - 1]} al {b.day} de {estilo.MESES[b.month - 1]}"


def responder(id_, estado, nombre):
    db.ejecutar("UPDATE vacaciones_solicitudes SET estado = :e, resuelto_por = :q WHERE id = :id",
                {"e": estado, "q": sesion.get("nombre") or sesion.get("usuario"), "id": int(id_)})
    st.session_state["ini_aviso"] = f"Vacaciones de {estilo.bonito(nombre)}: {'aprobadas' if estado == 'APROBADA' else 'rechazadas'}."


if rol in ("jefe", "admin"):
    if "ini_aviso" in st.session_state:
        st.success(st.session_state.pop("ini_aviso"))
    todos = db.consultar("SELECT cod, nombre, area, seccion FROM rrhh_personal")
    jefes = jefes_por_area(todos)
    sols = db.consultar("SELECT id, cod, inicio, fin, dias, estado FROM vacaciones_solicitudes "
                        "WHERE estado LIKE 'PENDIENTE%' ORDER BY inicio").merge(todos[["cod", "nombre", "area"]], on="cod")
    tele_p = db.consultar("SELECT cod FROM teletrabajo_solicitudes WHERE estado = 'PENDIENTE'").merge(todos[["cod", "area"]], on="cod")
    if rol == "jefe":
        mis = [a for a, c in jefes.items() if c == mi_cod]
        pend = sols[sols["area"].isin(mis) & (sols["estado"] == "PENDIENTE") & (sols["cod"] != mi_cod)
                    & ~sols["cod"].isin(set(jefes.values()))]
        tele_p = tele_p[tele_p["area"].isin(mis) & (tele_p["cod"] != mi_cod)]
        alcance = todos[todos["area"].isin(mis)]
    else:
        pend, alcance = sols, todos

    st.markdown(f'<div class="a-cab"><b>Por aprobar</b><span>{len(pend)} '
                f'{"solicitud" if len(pend) == 1 else "solicitudes"} de vacaciones</span></div>', unsafe_allow_html=True)
    if pend.empty:
        st.markdown('<div class="h-panel" style="color:var(--h-suave)">No hay vacaciones esperando tu respuesta.</div>',
                    unsafe_allow_html=True)
    for r in pend.head(4).itertuples():
        faltan = (date.fromisoformat(r.inicio) - hoy).days
        cuando = ("Empieza hoy" if faltan == 0 else "Empieza mañana" if faltan == 1 else
                  f"Empieza en {faltan} días" if faltan > 1 else "La fecha de inicio ya pasó")
        extra = " " + estilo.estado_html("La aprueba gerencia", "espera") if r.estado == "PENDIENTE_GERENCIA" else ""
        with st.container(border=True, key=f"{'inu' if faltan <= 7 else 'ini'}_{r.id}"):
            st.markdown(f'<div class="i-ped"><span class="h-iniciales">{html.escape(estilo.iniciales(r.nombre))}</span>'
                        f'<div><b>{html.escape(estilo.bonito(r.nombre))}</b><small>Vacaciones {rango(r.inicio, r.fin)}, '
                        f'{int(r.dias)} {"día" if r.dias == 1 else "días"}. {cuando}.</small>{extra}</div></div>',
                        unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            b1.button("Rechazar", key=f"ini_re_{r.id}", use_container_width=True,
                      on_click=responder, args=(r.id, "RECHAZADA", r.nombre))
            b2.button("Aprobar", key=f"ini_ap_{r.id}", type="primary", use_container_width=True,
                      on_click=responder, args=(r.id, "APROBADA", r.nombre))
    otros = []
    if len(pend) > 4:
        otros.append((f"y {len(pend) - 4} más", "paginas/aprobaciones.py", "Ver todas"))
    if not tele_p.empty:
        n = tele_p["cod"].nunique()
        otros.append((f"Teletrabajo de {n} {'persona' if n == 1 else 'personas'} por aprobar", "paginas/aprobaciones.py", "Revisar"))
    if rol == "admin":
        fac = db.consultar("SELECT estado, fecha_vencimiento FROM facturas_proveedores WHERE estado IN ('PENDIENTE','APROBADA','OBSERVADA')")
        venc = int((fac["fecha_vencimiento"].fillna("9999") < hoy.isoformat()).sum()) if not fac.empty else 0
        por_ap = int((fac["estado"] == "PENDIENTE").sum()) if not fac.empty else 0
        usu = db.uno("SELECT COUNT(*) AS n FROM usuarios WHERE estado = 'PENDIENTE'").n
        if venc:
            otros.append((f"{venc} {'factura vencida' if venc == 1 else 'facturas vencidas'} sin pagar", "paginas/facturas.py", "Ver"))
        if por_ap:
            otros.append((f"{por_ap} {'factura' if por_ap == 1 else 'facturas'} por aprobar", "paginas/facturas.py", "Ver"))
        if usu:
            otros.append((f"{usu} {'usuario nuevo' if usu == 1 else 'usuarios nuevos'} por aprobar", "paginas/perfiles.py", "Ver"))
    for k, (texto, pagina, boton) in enumerate(otros):
        with st.container(key=f"iox_{k}"):
            c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
            c1.markdown(texto)
            c2.page_link(pagina, label=boton, icon=":material/arrow_forward:")

    # Quién está fuera hoy
    iso_h = hoy.isoformat()
    cods = set(alcance["cod"])
    fuera = db.consultar("SELECT DISTINCT cod FROM vacaciones_solicitudes WHERE estado = 'APROBADA' AND inicio <= :h AND fin >= :h",
                         {"h": iso_h})
    casa = db.consultar("SELECT DISTINCT cod FROM teletrabajo_solicitudes WHERE estado = 'APROBADO' AND fecha = :h", {"h": iso_h})
    nombres = dict(zip(todos["cod"], todos["nombre"]))
    chips_v = "".join(estilo.estado_html(estilo.nombre_pila(nombres[c]) + " " + nombres[c].split(",")[0].split()[0].title(), "info")
                      for c in fuera["cod"] if c in cods)
    chips_t = "".join(estilo.estado_html(estilo.nombre_pila(nombres[c]) + " " + nombres[c].split(",")[0].split()[0].title(), "ok")
                      for c in casa["cod"] if c in cods)
    st.markdown(f'<div class="h-panel" style="margin-top:12px"><h3>Hoy en tu equipo</h3>'
                f'<p class="i-mini">De vacaciones</p><div class="i-chips">{chips_v or "<span class=i-nadie>Nadie</span>"}</div>'
                f'<p class="i-mini">En teletrabajo</p><div class="i-chips">{chips_t or "<span class=i-nadie>Nadie</span>"}</div></div>',
                unsafe_allow_html=True)
    if ficha:
        st.markdown('<div class="a-cab" style="margin-top:18px"><b>Lo tuyo</b></div>', unsafe_allow_html=True)

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
    cab = "".join(f'<th class="{"hoy" if d == hoy else ""}"><span class="i-dl">{estilo.DIAS_CORTOS[d.weekday()]}</span>'
                  f'<span class="i-dc">{estilo.DIAS_CORTOS[d.weekday()][0]}</span> {d.day}</th>' for d in dias)
    filas = []
    for p in equipo.itertuples():
        celdas = []
        for d in dias:
            iso = d.isoformat()
            v = solicitudes[(solicitudes["cod"] == p.cod) & (solicitudes["inicio"] <= iso) & (solicitudes["fin"] >= iso)]
            if iso in fer:
                celdas.append('<td class="fer"><span class="i-dl">Feriado</span><span class="i-dc">F</span></td>')
            elif not v.empty:
                clase = "vac" if (v["estado"] == "APROBADA").any() else "vacp"
                celdas.append(f'<td class="{clase}"><span class="i-dl">Vac.</span><span class="i-dc">V</span></td>')
            elif ((tele["cod"] == p.cod) & (tele["fecha"] == iso)).any():
                celdas.append('<td class="tele"><span class="i-dl">Casa</span><span class="i-dc">C</span></td>')
            else:
                celdas.append("<td></td>")
        corto = f"{estilo.nombre_pila(p.nombre)} {str(p.nombre).split(',')[0].split()[0].title()}"
        filas.append(f"<tr><td title=\"{html.escape(estilo.bonito(p.nombre))}\">{html.escape(corto)}</td>{''.join(celdas)}</tr>")
    st.markdown(f"""<div class="h-panel"><h3>{html.escape(titulo_eq)}</h3>
<table class="i-semana"><thead><tr><th></th>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>
<div class="i-ley2"><span class="h-estado info">Vac. (V) = vacaciones</span><span class="h-estado info">Casa (C) = teletrabajo</span>
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
