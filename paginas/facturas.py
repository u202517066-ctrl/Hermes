import html
import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import text

import db
from lector_facturas import VERSION, clave_api, leer_archivo

st.markdown(
    """
<style>
.fa-banda {
  background: #0B4F9C; color: #FFFFFF; border-radius: 14px;
  padding: 1.2rem 1.6rem; display: flex; justify-content: space-between;
  align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.8rem;
}
.fa-banda h2 { color: #FFFFFF; margin: 0; padding: 0; font-size: 1.6rem; font-weight: 600; }
.fa-banda p { margin: 0.25rem 0 0; opacity: 0.85; }
.fa-num { text-align: right; line-height: 1.1; }
.fa-num b { font-size: 2.4rem; display: block; }
.fa-num span { opacity: 0.85; font-size: 0.95rem; }
/* Sin botones − / +: los montos leídos de la factura solo se corrigen escribiendo */
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none; }
</style>
""",
    unsafe_allow_html=True,
)

DIAS_ALERTA = 7  # avisar las que vencen en los próximos 7 días
SIMBOLO = {"PEN": "S/", "USD": "US$"}
ESTADOS = {"PENDIENTE": "Por pagar", "PAGADA": "Pagada", "ANULADA": "Anulada"}

st.title("Facturas")
sesion = st.session_state.get("sesion", {})
if sesion.get("rol") != "admin":
    st.error("Solo el administrador puede ver esta página.")
    st.stop()

hoy = db.hoy()
if "fa_aviso" in st.session_state:
    st.success(st.session_state.pop("fa_aviso"))


# ---------- Utilidades ----------
def dinero(monto, moneda):
    return f"{SIMBOLO.get(moneda, moneda or '')} {monto:,.2f}".strip()


def totales_por_moneda(df):
    if df.empty:
        return "S/ 0.00"
    return " y ".join(dinero(v, m) for m, v in df.groupby("moneda")["total"].sum().items())


def fecha_corta(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


def cargar():
    df = db.consultar("SELECT * FROM facturas_proveedores ORDER BY fecha_vencimiento, proveedor")
    for c in ("subtotal", "igv", "total"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df["moneda"] = df["moneda"].fillna("PEN")
    vencida = (df["estado"] == "PENDIENTE") & (df["fecha_vencimiento"].fillna("9999") < hoy.isoformat())
    df["situacion"] = df["estado"].map(ESTADOS).where(~vencida, "Vencida")
    return df


def guardar(filas):
    """Guarda las facturas nuevas con su detalle y omite las repetidas (mismo RUC y comprobante).
    Cada fila puede traer 'items': [{descripcion, cantidad, valor_unitario, importe}]. Devuelve (guardadas, repetidas)."""
    existentes = db.consultar("SELECT ruc, comprobante FROM facturas_proveedores")
    claves = {(str(r or "").strip(), str(c or "").strip().upper())
              for r, c in zip(existentes["ruc"], existentes["comprobante"])}
    guardadas, repetidas = 0, []
    with db.motor().begin() as con:
        for f in filas:
            clave = (str(f["ruc"] or "").strip(), str(f["comprobante"] or "").strip().upper())
            if clave in claves:
                repetidas.append(f["comprobante"])
                continue
            claves.add(clave)
            datos = {k: v for k, v in f.items() if k != "items"}
            factura_id = con.execute(text(
                "INSERT INTO facturas_proveedores (ruc, proveedor, comprobante, fecha_emision, fecha_vencimiento, "
                "moneda, subtotal, igv, total, estado, observacion, archivo, creado) VALUES (:ruc, :proveedor, "
                ":comprobante, :fecha_emision, :fecha_vencimiento, :moneda, :subtotal, :igv, :total, 'PENDIENTE', "
                ":observacion, :archivo, :creado) RETURNING id"), {**datos, "creado": db.ahora()}).scalar()
            items = [it for it in f.get("items", []) if it.get("descripcion") or it.get("importe")]
            if items:
                con.execute(text(
                    "INSERT INTO facturas_items (factura_id, n, descripcion, cantidad, valor_unitario, importe) "
                    "VALUES (:factura_id, :n, :descripcion, :cantidad, :valor_unitario, :importe)"),
                    [{**it, "factura_id": factura_id, "n": i} for i, it in enumerate(items, start=1)])
            guardadas += 1
    return guardadas, repetidas


def cargar_items(ids=None):
    df = db.consultar("SELECT * FROM facturas_items ORDER BY factura_id, n")
    for c in ("cantidad", "valor_unitario", "importe"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df if ids is None else df[df["factura_id"].isin(ids)]


@st.cache_data(show_spinner=False, max_entries=300)
def leer(nombre, contenido, version):
    """Se guarda en memoria para no releer cada vez que se edita una celda.
    'version' hace que, al actualizar el lector, las facturas se vuelvan a leer."""
    return leer_archivo(nombre, contenido)


def limpiar_items(df):
    items = []
    for r in df.to_dict("records"):
        v = {k: (None if pd.isna(x) else x) for k, x in r.items()}
        if v["Descripción"] or v["Importe"]:
            items.append({"descripcion": v["Descripción"], "cantidad": v["Cantidad"],
                          "valor_unitario": v["Valor unitario"], "importe": v["Importe"]})
    return items


COLS_ITEMS = {
    "Descripción": st.column_config.TextColumn("Descripción", width="large"),
    "Cantidad": st.column_config.NumberColumn("Cantidad", format="%.2f"),
    "Valor unitario": st.column_config.NumberColumn("Valor unitario", format="%.2f"),
    "Importe": st.column_config.NumberColumn("Importe", format="%.2f"),
}


def tabla_items(items):
    return pd.DataFrame(items or [{"descripcion": None, "cantidad": None, "valor_unitario": None, "importe": None}]) \
        .rename(columns={"descripcion": "Descripción", "cantidad": "Cantidad",
                         "valor_unitario": "Valor unitario", "importe": "Importe"})[list(COLS_ITEMS)]


def excel(df):
    """Excel con el listado filtrado (hoja Facturas) y el detalle de servicios (hoja Detalle)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas"
    azul, borde = "0B4F9C", Side(style="thin", color="D5E2F3")
    columnas = ["Proveedor", "RUC", "Comprobante", "Fecha emisión", "Fecha vencimiento", "Moneda",
                "Subtotal", "IGV", "Total", "Estado", "Fecha de pago", "Observación"]
    anchos = [34, 14, 16, 14, 17, 9, 14, 12, 14, 12, 14, 30]

    ws["A1"] = "FACTURAS DE PROVEEDORES"
    ws["A1"].font = Font(bold=True, size=14, color=azul)
    ws["A2"] = f"Generado el {hoy:%d/%m/%Y}"
    ws["A2"].font = Font(italic=True, color="6A7C99")
    for i, (titulo, ancho) in enumerate(zip(columnas, anchos), start=1):
        c = ws.cell(row=4, column=i, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", start_color=azul)
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = ancho

    fila = 5
    for r in df.itertuples():
        valores = [
            r.proveedor, r.ruc, r.comprobante,
            date.fromisoformat(r.fecha_emision) if r.fecha_emision else None,
            date.fromisoformat(r.fecha_vencimiento) if r.fecha_vencimiento else None,
            r.moneda, float(r.subtotal), float(r.igv), float(r.total), r.situacion,
            date.fromisoformat(r.fecha_pago) if r.fecha_pago else None, r.observacion,
        ]
        for col, v in enumerate(valores, start=1):
            c = ws.cell(row=fila, column=col, value=v)
            c.border = Border(bottom=borde)
            if col in (4, 5, 11):
                c.number_format = "dd/mm/yyyy"
            elif col in (7, 8, 9):
                c.number_format = "#,##0.00"
        fila += 1

    ultima = fila - 1
    if ultima >= 5:
        fila += 1
        for moneda in sorted(df["moneda"].unique()):
            ws.cell(row=fila, column=8, value=f"Total {moneda}").font = Font(bold=True)
            c = ws.cell(row=fila, column=9, value=f'=SUMIF(F5:F{ultima},"{moneda}",I5:I{ultima})')
            c.font, c.number_format = Font(bold=True), "#,##0.00"
            fila += 1
        ws.auto_filter.ref = f"A4:L{ultima}"
    ws.freeze_panes = "A5"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    # Hoja 2: una fila por servicio
    wd = wb.create_sheet("Detalle")
    cols_d = ["Proveedor", "RUC", "Comprobante", "Fecha emisión", "Moneda", "N.°", "Descripción",
              "Cantidad", "Valor unitario", "Importe"]
    for i, (titulo, ancho) in enumerate(zip(cols_d, [34, 14, 16, 14, 9, 6, 50, 11, 15, 14]), start=1):
        c = wd.cell(row=1, column=i, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", start_color=azul)
        c.alignment = Alignment(horizontal="center", vertical="center")
        wd.column_dimensions[get_column_letter(i)].width = ancho
    items = cargar_items(df["id"].tolist())
    cab = df.set_index("id")
    fila = 2
    for it in items.itertuples():
        f = cab.loc[it.factura_id]
        valores = [f["proveedor"], f["ruc"], f["comprobante"],
                   date.fromisoformat(f["fecha_emision"]) if f["fecha_emision"] else None, f["moneda"],
                   it.n, it.descripcion,
                   None if pd.isna(it.cantidad) else float(it.cantidad),
                   None if pd.isna(it.valor_unitario) else float(it.valor_unitario),
                   None if pd.isna(it.importe) else float(it.importe)]
        for col, v in enumerate(valores, start=1):
            c = wd.cell(row=fila, column=col, value=v)
            c.border = Border(bottom=borde)
            if col == 4:
                c.number_format = "dd/mm/yyyy"
            elif col in (8, 9, 10):
                c.number_format = "#,##0.00"
            elif col == 7:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        fila += 1
    if fila > 2:
        wd.auto_filter.ref = f"A1:J{fila - 1}"
    wd.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------- Resumen y alertas ----------
facturas = cargar()
por_pagar = facturas[facturas["estado"] == "PENDIENTE"]
vencidas = facturas[facturas["situacion"] == "Vencida"]
limite = (hoy + timedelta(days=DIAS_ALERTA)).isoformat()
proximas = por_pagar[(por_pagar["fecha_vencimiento"] >= hoy.isoformat()) & (por_pagar["fecha_vencimiento"] <= limite)]

st.markdown(
    f"""<div class="fa-banda">
  <div><h2>Facturas de proveedores</h2><p>{len(por_pagar)} por pagar</p></div>
  <div class="fa-num"><b>{html.escape(totales_por_moneda(por_pagar))}</b><span>pendiente de pago</span></div>
</div>""",
    unsafe_allow_html=True,
)


def detalle(df, verbo):
    partes = [f"{r.proveedor} ({r.comprobante}, {dinero(r.total, r.moneda)}, {verbo} el {fecha_corta(r.fecha_vencimiento)})"
              for r in df.head(5).itertuples()]
    extra = f" y {len(df) - 5} más" if len(df) > 5 else ""
    return "; ".join(partes) + extra


if not vencidas.empty:
    st.error(f"**{len(vencidas)} {'factura vencida' if len(vencidas) == 1 else 'facturas vencidas'}** "
             f"por {totales_por_moneda(vencidas)}: {detalle(vencidas, 'venció')}.")
if not proximas.empty:
    st.warning(f"**{len(proximas)} {'vence' if len(proximas) == 1 else 'vencen'} en los próximos {DIAS_ALERTA} días** "
               f"por {totales_por_moneda(proximas)}: {detalle(proximas, 'vence')}.")

tab_reg, tab_cargar, tab_mano = st.tabs(["Registro", "Cargar facturas", "Agregar a mano"])

# ---------- Registro ----------
with tab_reg:
    if facturas.empty:
        st.info("Todavía no hay facturas. Cárgalas en la pestaña «Cargar facturas».")
    else:
        f1, f2, f3 = st.columns(3)
        situacion = f1.selectbox("Estado", ["Todas", "Por pagar", "Vencida", "Pagada", "Anulada"])
        meses = sorted({f[:7] for f in facturas["fecha_vencimiento"].dropna()}, reverse=True)
        mes = f2.selectbox("Mes de vencimiento", ["Todos"] + meses,
                           format_func=lambda m: m if m == "Todos" else f"{m[5:]}/{m[:4]}")
        buscar = f3.text_input("Buscar proveedor, RUC o comprobante")

        vista = facturas
        if situacion == "Por pagar":
            vista = vista[vista["estado"] == "PENDIENTE"]
        elif situacion != "Todas":
            vista = vista[vista["situacion"] == situacion]
        if mes != "Todos":
            vista = vista[vista["fecha_vencimiento"].fillna("").str.startswith(mes)]
        if buscar:
            b = buscar.strip().lower()
            vista = vista[vista[["proveedor", "ruc", "comprobante"]].fillna("").apply(
                lambda r: b in " ".join(r).lower(), axis=1)]

        tabla = pd.DataFrame({
            "Elegir": False,
            "Proveedor": vista["proveedor"],
            "Comprobante": vista["comprobante"],
            "Emisión": vista["fecha_emision"].map(fecha_corta),
            "Vence": vista["fecha_vencimiento"].map(fecha_corta),
            "Total": [dinero(t, m) for t, m in zip(vista["total"], vista["moneda"])],
            "Estado": vista["situacion"],
            "Pagada el": vista["fecha_pago"].map(fecha_corta),
            "id": vista["id"],
        })
        editado = st.data_editor(
            tabla, key="fa_tabla", hide_index=True, width="stretch",
            column_order=["Elegir", "Proveedor", "Comprobante", "Emisión", "Vence", "Total", "Estado", "Pagada el"],
            disabled=["Proveedor", "Comprobante", "Emisión", "Vence", "Total", "Estado", "Pagada el"],
            column_config={"Elegir": st.column_config.CheckboxColumn("Elegir", width="small")},
        )
        st.caption(f"{len(vista)} {'factura' if len(vista) == 1 else 'facturas'}. Total: {totales_por_moneda(vista)}")
        ids = [int(i) for i in editado[editado["Elegir"]]["id"]]

        a1, a2, a3, a4, a5 = st.columns([2, 2, 2, 2, 2])
        fecha_pago = a1.date_input("Fecha de pago", value=hoy, format="DD/MM/YYYY", label_visibility="collapsed")

        def actualizar(sql, extra, mensaje):
            with db.motor().begin() as con:
                con.execute(text(sql), [{"id": i, **extra} for i in ids])
            st.session_state["fa_aviso"] = mensaje
            st.rerun()

        n = f"{len(ids)} {'factura' if len(ids) == 1 else 'facturas'}"
        if a2.button("Marcar pagada", type="primary", disabled=not ids):
            actualizar("UPDATE facturas_proveedores SET estado = 'PAGADA', fecha_pago = :f WHERE id = :id",
                       {"f": fecha_pago.isoformat()}, f"{n} marcada(s) como pagada(s).")
        if a3.button("Volver a por pagar", disabled=not ids):
            actualizar("UPDATE facturas_proveedores SET estado = 'PENDIENTE', fecha_pago = NULL WHERE id = :id",
                       {}, f"{n} de vuelta a por pagar.")
        if a4.button("Anular", disabled=not ids):
            actualizar("UPDATE facturas_proveedores SET estado = 'ANULADA' WHERE id = :id", {}, f"{n} anulada(s).")
        if a5.button("Eliminar", disabled=not ids):
            st.session_state["fa_confirmar"] = ids
        if st.session_state.get("fa_confirmar") and st.session_state["fa_confirmar"] == ids:
            st.warning(f"¿Eliminar {n}? Esta acción no se puede deshacer.")
            if st.button("Sí, eliminar"):
                st.session_state.pop("fa_confirmar")
                with db.motor().begin() as con:
                    con.execute(text("DELETE FROM facturas_items WHERE factura_id = :id"), [{"id": i} for i in ids])
                actualizar("DELETE FROM facturas_proveedores WHERE id = :id", {}, f"{n} eliminada(s).")

        if len(ids) == 1:
            f = facturas[facturas["id"] == ids[0]].iloc[0]
            with st.expander(f"Editar {f['comprobante']} ({f['proveedor']})", expanded=True):
                e1, e2, e3 = st.columns([3, 2, 2])
                n_prov = e1.text_input("Proveedor", f["proveedor"] or "", key=f"ed_p_{ids[0]}")
                n_ruc = e2.text_input("RUC", f["ruc"] or "", key=f"ed_r_{ids[0]}")
                n_comp = e3.text_input("Comprobante", f["comprobante"] or "", key=f"ed_c_{ids[0]}")
                e4, e5, e6 = st.columns(3)
                n_emi = e4.date_input("Emisión", date.fromisoformat(f["fecha_emision"]) if f["fecha_emision"] else hoy,
                                      format="DD/MM/YYYY", key=f"ed_e_{ids[0]}")
                n_ven = e5.date_input("Vence", date.fromisoformat(f["fecha_vencimiento"]) if f["fecha_vencimiento"] else hoy,
                                      format="DD/MM/YYYY", key=f"ed_v_{ids[0]}")
                n_mon = e6.selectbox("Moneda", ["PEN", "USD"], index=1 if f["moneda"] == "USD" else 0, key=f"ed_m_{ids[0]}")
                e7, e8, e9 = st.columns(3)
                n_sub = e7.number_input("Subtotal", value=float(f["subtotal"]), min_value=0.0, format="%.2f", key=f"ed_s_{ids[0]}")
                n_igv = e8.number_input("IGV", value=float(f["igv"]), min_value=0.0, format="%.2f", key=f"ed_i_{ids[0]}")
                n_tot = e9.number_input("Total", value=float(f["total"]), min_value=0.0, format="%.2f", key=f"ed_t_{ids[0]}")
                n_obs = st.text_input("Observación", f["observacion"] or "", key=f"ed_o_{ids[0]}")
                if st.button("Guardar cambios", type="primary", key=f"ed_g_{ids[0]}"):
                    if n_ven < n_emi:
                        st.error("La fecha de vencimiento es anterior a la de emisión.")
                    elif not n_prov.strip() or not n_comp.strip() or n_tot <= 0:
                        st.error("Completa proveedor, comprobante y total.")
                    else:
                        db.ejecutar(
                            "UPDATE facturas_proveedores SET proveedor = :p, ruc = :r, comprobante = :c, "
                            "fecha_emision = :e, fecha_vencimiento = :v, moneda = :m, subtotal = :s, igv = :i, "
                            "total = :t, observacion = :o WHERE id = :id",
                            {"p": n_prov.strip(), "r": n_ruc.strip() or None, "c": n_comp.strip().upper(),
                             "e": n_emi.isoformat(), "v": n_ven.isoformat(), "m": n_mon, "s": n_sub, "i": n_igv,
                             "t": n_tot, "o": n_obs.strip() or None, "id": ids[0]},
                        )
                        st.session_state["fa_aviso"] = f"Factura {n_comp.strip().upper()} actualizada."
                        st.rerun()
        elif ids:
            st.caption("Para editar una factura, marca solo una.")

        with st.expander("Ver el detalle de servicios de una factura"):
            opciones = {f"{r.proveedor} · {r.comprobante}": int(r.id) for r in vista.itertuples()}
            if opciones:
                elegida = opciones[st.selectbox("Factura", list(opciones))]
                det = cargar_items([elegida])
                if det.empty:
                    st.caption("Esta factura no tiene detalle de servicios registrado.")
                else:
                    st.dataframe(tabla_items(det.to_dict("records")), hide_index=True, width="stretch",
                                 column_config=COLS_ITEMS)

        st.download_button(
            "Descargar en Excel",
            data=excel(vista),
            file_name=f"facturas_proveedores_{hoy:%Y-%m-%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=vista.empty,
        )

# ---------- Cargar facturas (lectura automática) ----------
with tab_cargar:
    st.markdown("Sube una o varias facturas en **PDF** o **XML** (también el ZIP que manda el proveedor). "
                "El sistema busca la tabla de cada factura, sea cual sea el formato del proveedor, y saca los montos "
                "y el detalle de servicios. **Revisa antes de guardar**: con el XML la lectura es exacta; con el PDF "
                "puede haber algo que corregir.")
    if clave_api():
        st.caption("Lectura con IA activada para PDF y fotos.")
    if "fa_subida" not in st.session_state:
        st.session_state["fa_subida"] = 0
    ronda = st.session_state["fa_subida"]
    archivos = st.file_uploader("Facturas", type=["pdf", "xml", "zip", "png", "jpg", "jpeg", "webp"],
                                accept_multiple_files=True, key=f"fa_archivos_{ronda}")
    revisadas = []
    for k, a in enumerate(archivos or []):
        with st.spinner(f"Leyendo {a.name}..."):
            datos, nota = leer(a.name, a.getvalue(), VERSION)
        with st.container(border=True):
            st.markdown(f"**{a.name}**  \n:gray[{nota}]")
            c1, c2, c3 = st.columns([3, 2, 2])
            proveedor = c1.text_input("Proveedor", datos["proveedor"] or "", key=f"fa_p_{ronda}_{k}")
            ruc = c2.text_input("RUC", datos["ruc"] or "", key=f"fa_r_{ronda}_{k}")
            comprobante = c3.text_input("Comprobante", datos["comprobante"] or "", key=f"fa_c_{ronda}_{k}")
            c4, c5, c6 = st.columns(3)
            emision = c4.date_input("Emisión", date.fromisoformat(datos["fecha_emision"]) if datos["fecha_emision"] else None,
                                    format="DD/MM/YYYY", key=f"fa_e_{ronda}_{k}")
            vence = c5.date_input("Vence", date.fromisoformat(datos["fecha_vencimiento"]) if datos["fecha_vencimiento"] else None,
                                  format="DD/MM/YYYY", key=f"fa_v_{ronda}_{k}",
                                  help="Si queda vacío, se usa la fecha de emisión (pago al contado)")
            moneda = c6.selectbox("Moneda", ["PEN", "USD"], index=1 if datos["moneda"] == "USD" else 0,
                                  key=f"fa_m_{ronda}_{k}")
            c7, c8, c9 = st.columns(3)
            subtotal = c7.number_input("Subtotal", value=datos["subtotal"], min_value=0.0, format="%.2f",
                                       key=f"fa_s_{ronda}_{k}")
            igv = c8.number_input("IGV", value=datos["igv"], min_value=0.0, format="%.2f", key=f"fa_i_{ronda}_{k}")
            total = c9.number_input("Total", value=datos["total"], min_value=0.0, format="%.2f", key=f"fa_t_{ronda}_{k}")
            st.markdown("Detalle de servicios")
            items_df = st.data_editor(tabla_items(datos["items"]), key=f"fa_it_{ronda}_{k}", num_rows="dynamic",
                                      hide_index=True, width="stretch", column_config=COLS_ITEMS)
            items = limpiar_items(items_df)
            suma = round(sum(float(it["importe"] or 0) for it in items), 2)
            if items and subtotal and abs(suma - subtotal) > 0.05 and abs(suma - (total or 0)) > 0.05:
                st.caption(f":orange[La suma del detalle ({suma:,.2f}) no coincide con el subtotal ({subtotal:,.2f}) "
                           f"ni con el total. Revísalo.]")
            faltan = [n for n, v in (("proveedor", proveedor.strip()), ("comprobante", comprobante.strip()),
                                     ("emisión", emision), ("total", total)) if not v]
            if faltan:
                st.caption(":red[Falta completar: " + ", ".join(faltan) + "]")
            revisadas.append({"faltan": faltan, "fila": {
                "ruc": ruc.strip() or None, "proveedor": proveedor.strip(), "comprobante": comprobante.strip().upper(),
                "fecha_emision": emision.isoformat() if emision else None,
                "fecha_vencimiento": (vence or emision).isoformat() if (vence or emision) else None,
                "moneda": moneda, "subtotal": subtotal, "igv": igv, "total": total,
                "observacion": None, "archivo": a.name, "items": items,
            }})

    if revisadas:
        incompletas = sum(bool(r["faltan"]) for r in revisadas)
        if incompletas:
            st.warning(f"{incompletas} {'factura tiene' if incompletas == 1 else 'facturas tienen'} datos por completar.")
        if st.button(f"Guardar {len(revisadas)} {'factura' if len(revisadas) == 1 else 'facturas'}",
                     type="primary", disabled=bool(incompletas)):
            guardadas, repetidas = guardar([r["fila"] for r in revisadas])
            aviso = f"Listo: se {'guardó' if guardadas == 1 else 'guardaron'} {guardadas} " \
                    f"{'factura' if guardadas == 1 else 'facturas'}."
            if repetidas:
                aviso += f" Se omitieron por estar ya registradas: {', '.join(map(str, repetidas))}."
            st.session_state["fa_aviso"] = aviso
            st.session_state["fa_subida"] += 1  # limpia la carga
            st.rerun()

# ---------- Agregar a mano ----------
with tab_mano:
    with st.form("fa_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        proveedor = c1.text_input("Proveedor")
        ruc = c2.text_input("RUC", max_chars=11)
        c3, c4, c5 = st.columns(3)
        comprobante = c3.text_input("Comprobante", placeholder="F001-00000123")
        emision = c4.date_input("Fecha de emisión", value=hoy, format="DD/MM/YYYY")
        vence = c5.date_input("Fecha de vencimiento", value=hoy + timedelta(days=30), format="DD/MM/YYYY")
        c6, c7, c8, c9 = st.columns(4)
        moneda = c6.selectbox("Moneda", ["PEN", "USD"])
        subtotal = c7.number_input("Subtotal", min_value=0.0, step=10.0, format="%.2f")
        igv = c8.number_input("IGV", min_value=0.0, step=1.0, format="%.2f")
        total = c9.number_input("Total", min_value=0.0, step=10.0, format="%.2f",
                                help="Si lo dejas en 0, se calcula como subtotal + IGV")
        observacion = st.text_input("Observación (opcional)")
        st.markdown("Detalle de servicios (opcional)")
        items_m = st.data_editor(tabla_items([]), key="fa_items_mano", num_rows="dynamic", hide_index=True,
                                 width="stretch", column_config=COLS_ITEMS)
        if st.form_submit_button("Guardar factura", type="primary"):
            total = total or round(subtotal + igv, 2)
            if not proveedor.strip() or not comprobante.strip() or total <= 0:
                st.error("Completa proveedor, comprobante y total.")
            elif vence < emision:
                st.error("La fecha de vencimiento es anterior a la de emisión.")
            else:
                guardadas, repetidas = guardar([{
                    "ruc": ruc.strip() or None, "proveedor": proveedor.strip(),
                    "comprobante": comprobante.strip().upper(), "fecha_emision": emision.isoformat(),
                    "fecha_vencimiento": vence.isoformat(), "moneda": moneda, "subtotal": subtotal or None,
                    "igv": igv or None, "total": total, "observacion": observacion.strip() or None, "archivo": None,
                    "items": limpiar_items(items_m),
                }])
                if repetidas:
                    st.error("Esa factura ya está registrada (mismo RUC y comprobante).")
                else:
                    st.session_state["fa_aviso"] = f"Factura {comprobante.strip().upper()} guardada."
                    st.rerun()
