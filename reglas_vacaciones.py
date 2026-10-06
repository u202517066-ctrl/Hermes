"""Reglas de vacaciones de HERMES. Las usan las páginas de Vacaciones y Aprobaciones."""
import calendar
from datetime import date

# ---------- Reglas (se pueden ajustar aquí) ----------
DIAS_BLOQUE = 15                 # 30 días = 2 bloques de 15
TRAMOS_BLOQUE2 = (7, 8)          # el bloque 2 se toma en tramos corridos de 7 u 8 (el resto, aunque sea 1 día, también vale)
MESES_NORMALES = 10              # plazo normal desde el ingreso
MESES_CICLO = 12                 # los 2 últimos meses requieren aprobación de gerencia
TOPE_POR_GRUPO = 1               # retail: máx. de personas por grupo de vacaciones a la vez
TOPE_EJEC_SERVICIOS = 2          # retail: máx. de ejecutivos de servicios a la vez (1 o 2)


def sumar_meses(d, n):
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def aniversario(ingreso, anio):
    return date(anio, ingreso.month, min(ingreso.day, calendar.monthrange(anio, ingreso.month)[1]))


def primer_aniversario(ingreso):
    return sumar_meses(ingreso, 12)


def inicio_ciclo(ingreso, ref):
    """Aniversario más reciente (en o antes de ref): ese día se renuevan las vacaciones.
    Devuelve None si a esa fecha la persona todavía no cumple 1 año."""
    if ref < primer_aniversario(ingreso):
        return None
    a = aniversario(ingreso, ref.year)
    if a > ref:
        a = aniversario(ingreso, ref.year - 1)
    return a


def usados_en_ciclo(df, cod, c_ini, c_fin):
    mios = df[(df["cod"] == cod) & (df["inicio"] >= c_ini.isoformat()) & (df["inicio"] < c_fin.isoformat())]
    return {b: int(mios[mios["bloque"] == b]["dias"].sum()) for b in (1, 2)}


# ---------- Jefes por área ----------
# Área -> apellido del jefe que aprueba sus vacaciones (se busca en el nombre del personal).
# Para agregar un área, añade una línea. Las áreas que no estén aquí las aprueba el administrador.
APROBADORES = {
    "VENTAS": "BALDEON",
    "COMERCIAL SECTOR RETAIL Y SERVICIOS": "VILLAVICENC",
    "EXPERIENCIA DEL CLIENTE": "DESPOSORIO",
}


def jefes_por_area(personal):
    """{área: cod del jefe} según APROBADORES. Busca primero dentro del área y luego en todo el personal."""
    jefes = {}
    for area, apellido in APROBADORES.items():
        coincide = personal["nombre"].str.upper().str.contains(apellido, na=False, regex=False)
        m = personal[coincide & (personal["area"] == area)]
        if m.empty:
            m = personal[coincide]
        if not m.empty:
            jefes[area] = m.iloc[0]["cod"]
    return jefes
