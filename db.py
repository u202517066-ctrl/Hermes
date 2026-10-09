"""Conexión a la base de datos de HERMES.

- Sin DB_URL: usa el archivo local hermes.db (SQLite), en esta misma carpeta.
- Con DB_URL: usa PostgreSQL (Supabase o el servidor que indique TI).

DB_URL se busca, en este orden, en:
1. la variable de entorno DB_URL,
2. el archivo .streamlit/secrets.toml,
3. los Secrets de Streamlit Cloud.
Para pasar de uno a otro no hay que cambiar código, solo agregar o quitar DB_URL.
"""
import os
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError  # noqa: F401  (lo usan otros archivos)

CARPETA = Path(__file__).resolve().parent
ZONA = ZoneInfo("America/Lima")
_engine = None

VERSION_ESQUEMA = 3  # súbelo cuando se agreguen columnas, para que la app las cree al arrancar

# Columnas agregadas después de creadas las tablas: (tabla, columna, tipo)
COLUMNAS_NUEVAS = [
    ("facturas_proveedores", "aprobado_por", "TEXT"),
    ("facturas_proveedores", "fecha_aprobacion", "TEXT"),
    ("facturas_proveedores", "motivo_observacion", "TEXT"),
]

TABLAS = ["usuarios", "rrhh_personal", "vacaciones_solicitudes", "teletrabajo_solicitudes", "feriados",
          "facturas_proveedores", "facturas_items", "facturas_archivos"]

# El esquema está escrito para PostgreSQL; para SQLite se adapta solo el tipo del id.
ESQUEMA = [
    """CREATE TABLE IF NOT EXISTS usuarios (
        usuario TEXT PRIMARY KEY, sal TEXT, clave TEXT, rol TEXT, cod TEXT UNIQUE,
        nombre TEXT, apellido TEXT, estado TEXT DEFAULT 'ACTIVO')""",
    """CREATE TABLE IF NOT EXISTS rrhh_personal (
        id SERIAL PRIMARY KEY, cod TEXT, nombre TEXT, puesto TEXT, sexo TEXT,
        unidad TEXT, departamento TEXT, area TEXT, seccion TEXT,
        sede TEXT, sucursal TEXT, f_ingreso TEXT, mes_ingreso TEXT)""",
    """CREATE TABLE IF NOT EXISTS vacaciones_solicitudes (
        id SERIAL PRIMARY KEY, cod TEXT, inicio TEXT, fin TEXT, dias INTEGER,
        bloque INTEGER, estado TEXT, requiere_gerencia INTEGER DEFAULT 0,
        creado TEXT, resuelto_por TEXT)""",
    """CREATE TABLE IF NOT EXISTS teletrabajo_solicitudes (
        id SERIAL PRIMARY KEY, cod TEXT, fecha TEXT, estado TEXT,
        creado TEXT, resuelto_por TEXT)""",
    """CREATE TABLE IF NOT EXISTS feriados (
        fecha TEXT PRIMARY KEY, nombre TEXT)""",
    """CREATE TABLE IF NOT EXISTS facturas_proveedores (
        id SERIAL PRIMARY KEY, ruc TEXT, proveedor TEXT, comprobante TEXT,
        fecha_emision TEXT, fecha_vencimiento TEXT, moneda TEXT,
        subtotal NUMERIC(14,2), igv NUMERIC(14,2), total NUMERIC(14,2),
        estado TEXT, fecha_pago TEXT, observacion TEXT, archivo TEXT, creado TEXT)""",
    """CREATE TABLE IF NOT EXISTS facturas_archivos (
        id SERIAL PRIMARY KEY, factura_id INTEGER, nombre TEXT, tipo TEXT, contenido BYTEA)""",
    """CREATE TABLE IF NOT EXISTS facturas_items (
        id SERIAL PRIMARY KEY, factura_id INTEGER, n INTEGER, descripcion TEXT,
        cantidad NUMERIC(14,3), valor_unitario NUMERIC(14,4), importe NUMERIC(14,2))""",
]


def _leer_url():
    url = os.environ.get("DB_URL")
    archivo = CARPETA / ".streamlit" / "secrets.toml"
    if not url and archivo.exists():
        try:
            with open(archivo, "rb") as f:
                url = tomllib.load(f).get("DB_URL")
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(
                f"El archivo .streamlit/secrets.toml tiene un error ({e}). "
                "Corrígelo, o bórralo para trabajar con hermes.db."
            ) from None
    if not url:
        try:
            import streamlit as st
            url = st.secrets["DB_URL"]
        except Exception:
            url = None
    if not url or not url.strip():
        return "sqlite:///" + (CARPETA / "hermes.db").as_posix()
    url = url.strip()
    for prefijo in ("postgresql://", "postgres://"):
        if url.startswith(prefijo):
            url = "postgresql+psycopg://" + url[len(prefijo):]
    return url


def motor():
    global _engine
    if _engine is None:
        url = _leer_url()
        if url.startswith("sqlite"):
            _engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)
    return _engine


def es_local():
    """True si se está usando hermes.db (SQLite)."""
    return motor().dialect.name == "sqlite"


def consultar(sql, params=None):
    """Devuelve el resultado de un SELECT como tabla de pandas."""
    with motor().connect() as con:
        return pd.read_sql_query(text(sql), con, params=params or {})


def uno(sql, params=None):
    """Devuelve la primera fila de un SELECT (o None)."""
    with motor().connect() as con:
        return con.execute(text(sql), params or {}).fetchone()


def ejecutar(sql, params=None):
    """Ejecuta un INSERT, UPDATE o DELETE."""
    with motor().begin() as con:
        con.execute(text(sql), params or {})


def crear_tablas():
    local = es_local()
    with motor().begin() as con:
        for sql in ESQUEMA:
            if local:
                sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("BYTEA", "BLOB")
            con.execute(text(sql))
        from sqlalchemy import inspect
        revisor = inspect(con)
        for tabla, columna, tipo in COLUMNAS_NUEVAS:
            if columna not in {c["name"] for c in revisor.get_columns(tabla)}:
                con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"))
        if local:
            # hermes.db antiguos: agrega columnas que pudieran faltar
            columnas = {r[1] for r in con.execute(text("PRAGMA table_info(vacaciones_solicitudes)"))}
            if "resuelto_por" not in columnas:
                con.execute(text("ALTER TABLE vacaciones_solicitudes ADD COLUMN resuelto_por TEXT"))
        else:
            # Bloquea el acceso público de Supabase a estas tablas;
            # la app entra con la contraseña de la base, así que no le afecta.
            for t in TABLAS:
                con.execute(text(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"))


def hoy():
    return datetime.now(ZONA).date()


def ahora():
    return datetime.now(ZONA).strftime("%Y-%m-%dT%H:%M:%S")
