import calendar
import html
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
import estilo
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


DIAS_C = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def quitar_teletrabajo_en_vacaciones(cod, ini, fin):
    """Borra el teletrabajo (en espera o aprobado) de las semanas en que la persona sale de vacaciones.
    Cuenta la semana si las vacaciones tocan algún día de lunes a viernes. Devuelve las fechas quitadas."""
    fechas, lun = [], ini - timedelta(days=ini.weekday())
    while lun <= fin:
        if ini <= lun + timedelta(days=4) and fin >= lun:
            tele = db.consultar(
                "SELECT id, fecha FROM teletrabajo_solicitudes WHERE cod = :c AND fecha >= :a AND fecha <= :b "
                "AND estado <> 'RECHAZADO'",
                {"c": cod, "a": lun.isoformat(), "b": (lun + timedelta(days=6)).isoformat()},
            )
            for i, f in zip(tele["id"], tele["fecha"]):
                db.ejecutar("DELETE FROM teletrabajo_solicitudes WHERE id = :id", {"id": int(i)})
                fechas.append(date.fromisoformat(f))
        lun += timedelta(days=7)
    return sorted(fechas)


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


def en_grupo(fila):
    """Restricciones solo para retail y solo para quienes están en un grupo (GRUPO_1, GRUPO_2, GRUPO_3)."""
    return es_retail(fila) and str(fila.get("seccion", "")).upper().startswith("GRUPO")


def teletrabajo_en_semanas(cod, ini, fin):
    """Teletrabajo (no rechazado) en las semanas de lunes a viernes que tocan las vacaciones."""
    fechas, lun = [], ini - timedelta(days=ini.weekday())
    while lun <= fin:
        if ini <= lun + timedelta(days=4) and fin >= lun:
            t = db.consultar("SELECT fecha FROM teletrabajo_solicitudes WHERE cod = :c AND fecha >= :a AND fecha <= :b "
                             "AND estado <> 'RECHAZADO'", {"c": cod, "a": lun.isoformat(),
                                                           "b": (lun + timedelta(days=6)).isoformat()})
            fechas += [date.fromisoformat(f) for f in t["fecha"]]
        lun += timedelta(days=7)
    return sorted(fechas)


def revisar(p, ingreso, ini, fin, es_admin):
    """Revisa todas las reglas. Devuelve (items, requiere_gerencia, bloque), donde items es una lista
    de (tipo, texto) con tipo 'si' (se cumple), 'ojo' (aviso) o 'no' (impide enviar)."""
    items = []
    if fin < ini:
        return [("no", "La fecha final es anterior a la inicial.")], False, None
    dias = (fin - ini).days + 1
    if ini < db.hoy() and not es_admin:
        items.append(("no", "La fecha de inicio ya pasó. Elige una fecha desde hoy."))

    c_ini = inicio_ciclo(ingreso, ini)
    c_hoy = inicio_ciclo(ingreso, db.hoy())
    if c_ini is None:
        return [("no", f"Solo se puede tomar vacaciones después de cumplir 1 año en la empresa "
                       f"(desde el {primer_aniversario(ingreso):%d/%m/%Y}).")], False, None
    if not es_admin and (c_hoy is None or c_ini > c_hoy):
        return [("no", "Esas fechas corresponden a tu próximo periodo. Podrás programarlas cuando se renueven "
                       "tus días, al cumplir un año más en la empresa.")], False, None
    limite, tope = sumar_meses(c_ini, MESES_NORMALES), sumar_meses(c_ini, MESES_CICLO)
    gerencia = False
    if fin >= tope:
        items.append(("no", "Estas fechas pasan el plazo máximo de tu periodo. Elige fechas más cercanas."))
    elif fin > limite:
        gerencia = True
        items.append(("ojo", "Caen en los últimos 2 meses de tu periodo: la solicitud la aprueba gerencia."))

    activas = solicitudes(solo_activas=True)
    usados = usados_en_ciclo(activas, p["cod"], c_ini, tope)
    libres = DIAS_PERIODO - usados[1] - usados[2]
    if dias > libres:
        items.append(("no", f"Te quedan {libres} días por programar y estás pidiendo {dias}."))
    else:
        items.append(("si", f"Te alcanzan los días: quedarías con {libres - dias}."))

    propias = activas[activas["cod"] == p["cod"]]
    if max_simultaneos(propias, ini, fin) > 0:
        items.append(("no", "Ya tienes vacaciones registradas que se cruzan con esas fechas."))
    else:
        items.append(("si", "No se cruza con otras vacaciones tuyas."))

    if en_grupo(p):
        otros = activas[activas["cod"] != p["cod"]]
        otros = otros[otros.apply(en_grupo, axis=1)] if not otros.empty else otros
        grupo = otros[otros["seccion"] == p["seccion"]]
        if max_simultaneos(grupo, ini, fin) >= TOPE_POR_GRUPO:
            items.append(("no", "Alguien de tu grupo ya tiene vacaciones en esas fechas. Prueba con otras."))
        else:
            items.append(("si", "Nadie de tu grupo sale esas fechas."))
        if str(p["puesto"]).upper() == "EJECUTIVO DE SERVICIOS":
            ejec = otros[otros["puesto"].str.upper() == "EJECUTIVO DE SERVICIOS"]
            problema = False
            if max_simultaneos(ejec, ini, fin) > 0:
                problema = True
                items.append(("no", "Otro ejecutivo de servicios ya tiene vacaciones en esas fechas. "
                                    "Deben salir en fechas distintas."))
            for m_ini, m_fin in meses_entre(ini, fin):
                en_mes = ejec[(ejec["inicio"] <= m_fin.isoformat()) & (ejec["fin"] >= m_ini.isoformat())]
                if en_mes["cod"].nunique() >= TOPE_EJEC_SERVICIOS:
                    problema = True
                    items.append(("no", f"En {MESES_ES[m_ini.month - 1]} ya salen {TOPE_EJEC_SERVICIOS} ejecutivos "
                                        "de servicios de vacaciones (es el máximo por mes). Prueba con otro mes."))
            if not problema:
                items.append(("si", "Cumple el máximo de ejecutivos de servicios por mes, sin cruzarse."))

    tele = teletrabajo_en_semanas(p["cod"], ini, fin)
    if tele:
        lista = ", ".join(f"{DIAS_C[d.weekday()]} {d:%d/%m}" for d in tele)
        items.append(("ojo", f"Tenías teletrabajo el {lista}; se quitará al enviar la solicitud."))
    return items, gerencia, 1


def validar(p, ingreso, ini, fin, es_admin):
    """Compatibilidad: devuelve (errores, requiere_gerencia, bloque)."""
    items, gerencia, bloque = revisar(p, ingreso, ini, fin, es_admin)
    return [t for k, t in items if k == "no"], gerencia, bloque


# ---------- Estilo ----------
st.markdown(
    """
<style>
.v-resumen { border-left: 4px solid var(--h-azul); background: var(--h-fondo); border-radius: 0 12px 12px 0;
  padding: 12px 16px; margin: 4px 0 14px; color: var(--h-tinta); }
.v-resumen b { font-size: 1.6rem; font-stretch: 75%; color: var(--h-azul); }
.v-rev { list-style: none; margin: 0 0 14px; padding: 0; }
.v-rev li { display: flex; gap: 10px; padding: 6px 0; align-items: flex-start; color: var(--h-tinta); }
.v-rev li::before { flex: none; width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center;
  font-size: 0.75rem; font-weight: 800; margin-top: 1px; }
.v-rev li.si::before { content: "✓"; background: var(--h-verde-suave); color: var(--h-verde); }
.v-rev li.ojo::before { content: "!"; background: var(--h-ambar-suave); color: var(--h-ambar-texto); }
.v-rev li.no::before { content: "✕"; background: var(--h-rojo-suave); color: var(--h-rojo); }
.v-rev li.no { color: var(--h-rojo); }
.v-mes, .v-mes * { border: 0 !important; box-shadow: none; }
.v-mes { width: 100%; border-collapse: separate !important; border-spacing: 4px; table-layout: fixed; margin: 0; }
.v-mes tr { background: transparent !important; }
.v-mes caption { text-align: left; font-weight: 700; font-size: 1.05rem; margin-bottom: 6px; color: var(--h-tinta); caption-side: top; }
.v-mes th { font-size: 0.78rem; color: var(--h-suave); font-weight: 600; padding: 2px 0; text-align: center; }
.v-mes td { height: 42px; text-align: center; border-radius: 9px; font-weight: 600; position: relative;
  vertical-align: middle; color: var(--h-tinta); }
.v-mes td.d { background: var(--h-fondo); }
.v-mes td.finde { color: var(--h-suave); }
.v-mes td.elegido { background: var(--h-azul); color: #FFFFFF; }
.v-mes td.fer { color: var(--h-rojo); text-decoration: line-through; background: var(--h-rojo-suave); }
.v-mes td.otro::after { content: ""; position: absolute; left: 25%; right: 25%; bottom: 6px; height: 3px;
  border-radius: 2px; background: var(--h-ambar); }
.v-mes td.hoy { box-shadow: inset 0 0 0 2px var(--h-azul) !important; }
.v-ley { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.82rem; color: var(--h-suave); margin-top: 8px; }
.v-ley span::before { content: ""; display: inline-block; width: 12px; height: 12px; border-radius: 3px; margin-right: 6px; vertical-align: -2px; }
.v-ley .e1::before { background: var(--h-azul); }
.v-ley .e2::before { background: var(--h-ambar); height: 3px; vertical-align: 2px; }
.v-ley .e3::before { background: var(--h-rojo-suave); outline: 1px solid var(--h-rojo); }
.v-hist { list-style: none; margin: 0; padding: 0; }
.v-hist li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--h-linea);
  align-items: center; color: var(--h-tinta); }
.v-hist li:last-child { border-bottom: 0; }
.v-hist small { color: var(--h-suave); display: block; }
.st-key-vac_form { background: var(--h-superficie); }
</style>
""",
    unsafe_allow_html=True,
)


def rango_texto(a, b):
    if a.month == b.month:
        return f"del {estilo.DIAS[a.weekday()]} {a.day} al {estilo.DIAS[b.weekday()]} {b.day} de {estilo.MESES[b.month - 1]}"
    return f"del {a.day} de {estilo.MESES[a.month - 1]} al {b.day} de {estilo.MESES[b.month - 1]}"


def calendario(anio, mes, ini, fin, feriados, otros, hoy):
    """Mes con el rango elegido, feriados, días en que sale alguien del grupo/equipo y el día de hoy."""
    filas = []
    for semana in calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes):
        celdas = []
        for d in semana:
            if d.month != mes:
                celdas.append("<td></td>")
                continue
            iso, clases = d.isoformat(), []
            if iso in feriados:
                clases.append("fer")
            elif ini <= d <= fin:
                clases.append("elegido")
            elif d.weekday() >= 5:
                clases.append("finde")
            else:
                clases.append("d")
            if not otros.empty and ((otros["inicio"] <= iso) & (otros["fin"] >= iso)).any() and d.weekday() < 5:
                clases.append("otro")
            if d == hoy:
                clases.append("hoy")
            titulo = f' title="{html.escape(feriados[iso])}"' if iso in feriados else ""
            celdas.append(f'<td class="{" ".join(clases)}"{titulo}>{d.day}</td>')
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    cab = "".join(f"<th>{x}</th>" for x in DIAS_C)
    return (f'<table class="v-mes"><caption>{estilo.MESES[mes - 1].capitalize()} {anio}</caption>'
            f"<thead><tr>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>")


# ---------- Pantalla ----------
st.title("Vacaciones")
sesion = st.session_state.get("sesion", {})
es_admin = sesion.get("rol") == "admin"

personal = cargar_personal()
if personal.empty:
    st.info("Todavía no hay personal cargado. El administrador debe cargar el Excel.")
    st.stop()

if es_admin:
    etiquetas = {f"{estilo.bonito(r.nombre)} ({r.cod})": r.cod for r in personal.itertuples()}
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
        st.markdown(f'<div class="h-panel"><h3>Todavía no puedes pedir vacaciones</h3>'
                    f'<p style="margin:0">Podrás programarlas desde el {primero:%d/%m/%Y}, cuando cumplas 1 año en la empresa.</p></div>',
                    unsafe_allow_html=True)
        st.stop()
    st.info(f"Esta persona todavía no cumple 1 año en la empresa. Solo se pueden registrar vacaciones desde el {primero:%d/%m/%Y}.")
    c_ini = primero
limite = sumar_meses(c_ini, MESES_NORMALES)
tope = sumar_meses(c_ini, MESES_CICLO)
activas = solicitudes(solo_activas=True)
usados = usados_en_ciclo(activas, p["cod"], c_ini, tope)
libres = max(DIAS_PERIODO - usados[1] - usados[2], 0)

aviso_plazo = ""
if libres and hoy > limite:
    aviso_plazo = " Ya pasó el plazo normal: lo que pidas ahora lo aprueba gerencia."
elif libres and (limite - hoy).days <= 60:
    aviso_plazo = " El plazo para tomarlos se acerca: te recomendamos programarlos pronto."
quien = "Tienes" if not es_admin else f"{estilo.bonito(p['nombre'])} tiene"
st.markdown(f'<div class="h-sub">{quien} {libres} {"día" if libres == 1 else "días"} por programar en este periodo.'
            f'{aviso_plazo}</div>', unsafe_allow_html=True)

if "vac_tele" in st.session_state:
    quitadas = st.session_state.pop("vac_tele")
    st.info("Se quitó el teletrabajo de las semanas de estas vacaciones: " + ", ".join(f"{d:%d/%m}" for d in quitadas) + ".")
if "vac_ok" in st.session_state:
    if st.session_state.pop("vac_ok"):
        st.success("Solicitud enviada. Como la aprueba gerencia, puede tardar un poco más.")
    else:
        st.success("Solicitud enviada. Tu jefe la verá en Aprobaciones.")

izq, der = st.columns([1, 1.1], gap="medium")
with izq, st.container(border=True, key="vac_form"):
    d1, d2 = st.columns(2)
    ini = d1.date_input("Desde", value=hoy, format="DD/MM/YYYY", key="vac_desde")
    fin = d2.date_input("Hasta", value=hoy + timedelta(days=6), format="DD/MM/YYYY", key="vac_hasta")
    items, gerencia, bloque = revisar(p, ingreso, ini, fin, es_admin)
    dias = (fin - ini).days + 1
    if dias > 0:
        st.markdown(f'<div class="v-resumen"><b>{dias} {"día" if dias == 1 else "días"}</b><br>'
                    f'{rango_texto(ini, fin).capitalize()}</div>', unsafe_allow_html=True)
    st.markdown('<ul class="v-rev">' + "".join(f'<li class="{k}">{html.escape(t)}</li>' for k, t in items) + "</ul>",
                unsafe_allow_html=True)
    errores = [t for k, t in items if k == "no"]
    if st.button("Enviar solicitud", type="primary", disabled=bool(errores), use_container_width=True):
        items, gerencia, bloque = revisar(p, ingreso, ini, fin, es_admin)  # se revisa otra vez al guardar
        if any(k == "no" for k, _ in items):
            st.error("Algo cambió mientras elegías las fechas. Revisa la lista de arriba.")
        else:
            db.ejecutar(
                "INSERT INTO vacaciones_solicitudes (cod, inicio, fin, dias, bloque, estado, requiere_gerencia, creado) "
                "VALUES (:cod, :inicio, :fin, :dias, :bloque, :estado, :rg, :creado)",
                {"cod": str(p["cod"]), "inicio": ini.isoformat(), "fin": fin.isoformat(), "dias": dias,
                 "bloque": int(bloque), "estado": "PENDIENTE_GERENCIA" if gerencia else "PENDIENTE",
                 "rg": int(gerencia), "creado": db.ahora()},
            )
            quitadas = quitar_teletrabajo_en_vacaciones(str(p["cod"]), ini, fin)
            st.session_state["vac_ok"] = gerencia
            if quitadas:
                st.session_state["vac_tele"] = quitadas
            st.rerun()

with der:
    feriados_df = db.consultar("SELECT fecha, nombre FROM feriados")
    feriados = dict(zip(feriados_df["fecha"], feriados_df["nombre"].fillna("Feriado")))
    otros = activas[activas["cod"] != p["cod"]]
    if en_grupo(p):
        otros = otros[otros["seccion"] == p["seccion"]]
        etiqueta_otros = "Sale alguien de tu grupo"
    else:
        otros = otros[otros["cod"].isin(personal[personal["area"] == p["area"]]["cod"])]
        etiqueta_otros = "Sale alguien de tu equipo"
    ref = ini if fin >= ini else hoy
    meses = [(ref.year, ref.month)]
    if fin >= ini and (fin.year, fin.month) != meses[0]:
        meses.append((fin.year, fin.month))
    tablas = "".join(calendario(a, m, ini, fin, feriados, otros, hoy) for a, m in meses)
    st.markdown(f'<div class="h-panel">{tablas}<div class="v-ley"><span class="e1">Tu solicitud</span>'
                f'<span class="e2">{etiqueta_otros}</span><span class="e3">Feriado</span></div></div>',
                unsafe_allow_html=True)

# Mis solicitudes
ESTADOS = {"PENDIENTE": ("Esperando a tu jefe", "espera"), "PENDIENTE_GERENCIA": ("Esperando a gerencia", "espera"),
           "APROBADA": ("Aprobada", "ok"), "RECHAZADA": ("Rechazada", "no")}
hist = solicitudes()
hist = hist[hist["cod"] == p["cod"]].sort_values("inicio", ascending=False)
if hist.empty:
    lista = '<p style="margin:0;color:var(--h-suave)">Todavía no hay solicitudes.</p>'
else:
    filas = []
    for r in hist.itertuples():
        a, b = date.fromisoformat(r.inicio), date.fromisoformat(r.fin)
        texto, tipo = ESTADOS.get(r.estado, (r.estado, "info"))
        detalle = f"{int(r.dias)} {'día' if r.dias == 1 else 'días'}"
        if isinstance(r.resuelto_por, str) and r.resuelto_por:
            detalle += f", {'aprobada' if r.estado == 'APROBADA' else 'respondida'} por {estilo.bonito(r.resuelto_por)}"
        filas.append(f"<li><div>{rango_texto(a, b).replace('del ', '', 1).capitalize()}<small>{html.escape(detalle)}</small></div>"
                     f"{estilo.estado_html(texto, tipo)}</li>")
    lista = '<ul class="v-hist">' + "".join(filas) + "</ul>"
st.markdown(f'<div class="h-panel" style="margin-top:14px"><h3>{"Mis solicitudes" if not es_admin else "Solicitudes"}</h3>{lista}</div>',
            unsafe_allow_html=True)
