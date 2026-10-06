import streamlit as st
from datetime import date, timedelta
from db import consultar, ejecutar

st.title("Vacaciones")

# ---------- Formulario para registrar solicitud ----------
empleados = consultar("SELECT id, nombre FROM empleados WHERE activo = 1 ORDER BY nombre")
ids = dict(zip(empleados["nombre"], empleados["id"]))

with st.expander("Registrar solicitud de vacaciones"):
    emp = st.selectbox("Empleado", list(ids.keys()))
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha de inicio", date.today())
    fin = c2.date_input("Fecha de fin", date.today() + timedelta(days=7))

    if st.button("Guardar solicitud"):
        if fin < inicio:
            st.error("La fecha de fin no puede ser anterior a la de inicio.")
        else:
            ejecutar(
                "INSERT INTO vacaciones (empleado_id, fecha_inicio, fecha_fin, estado) "
                "VALUES (?, ?, ?, 'Pendiente')",
                (int(ids[emp]), inicio.isoformat(), fin.isoformat()),
            )
            st.success("Solicitud registrada como Pendiente.")

# ---------- Filtros ----------
st.subheader("Listado")
f1, f2 = st.columns(2)
estado = f1.selectbox("Estado", ["Todos", "Pendiente", "Aprobada", "Rechazada"])
buscar = f2.text_input("Buscar empleado")

sql = (
    "SELECT v.id AS ID, e.nombre AS Empleado, e.area AS Area, "
    "v.fecha_inicio AS Inicio, v.fecha_fin AS Fin, "
    "CAST(julianday(v.fecha_fin) - julianday(v.fecha_inicio) + 1 AS INTEGER) AS Dias, "
    "v.estado AS Estado "
    "FROM vacaciones v JOIN empleados e ON e.id = v.empleado_id "
    "WHERE (? = 'Todos' OR v.estado = ?) AND e.nombre LIKE ? "
    "ORDER BY v.fecha_inicio DESC"
)
datos = consultar(sql, (estado, estado, "%" + buscar + "%"))

st.dataframe(datos, width="stretch", hide_index=True)
st.caption("{} registro(s)".format(len(datos)))

# ---------- Exportar (respeta los filtros) ----------
st.download_button(
    label="Exportar a CSV",
    data=datos.to_csv(index=False).encode("utf-8-sig"),
    file_name="vacaciones.csv",
    mime="text/csv",
)