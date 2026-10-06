import streamlit as st

import db

st.title("Directorio")


@st.cache_data(ttl=600)
def cargar():
    return db.consultar("SELECT * FROM rrhh_personal ORDER BY nombre")


df = cargar()

c1, c2, c3 = st.columns(3)
dep = c1.selectbox("Departamento", ["Todos"] + sorted(df["departamento"].dropna().unique().tolist()))
area = c2.selectbox("Área", ["Todas"] + sorted(df["area"].dropna().unique().tolist()))
buscar = c3.text_input("Buscar por nombre o código")

if dep != "Todos":
    df = df[df["departamento"] == dep]
if area != "Todas":
    df = df[df["area"] == area]
if buscar:
    df = df[
        df["nombre"].str.contains(buscar, case=False, na=False, regex=False)
        | df["cod"].str.contains(buscar, na=False, regex=False)
    ]

st.caption(f"{len(df)} personas")
st.dataframe(df.drop(columns=["id"]), width="stretch", hide_index=True)
