"""Revisa cómo se lee una factura. Uso:  py diagnostico_factura.py "ruta\\de\\la\\factura.pdf" """
import re
import sys

import lector_facturas as lf

ruta = sys.argv[1] if len(sys.argv) > 1 else input("Arrastra aquí el PDF y presiona Enter: ").strip().strip('"')
contenido = open(ruta, "rb").read()
try:
    import pymupdf
    print("pymupdf: instalado", pymupdf.__doc__.split(":")[0])
except ImportError:
    print("pymupdf: NO instalado  ->  ejecuta: py -m pip install pymupdf")
print("Versión del lector:", getattr(lf, "VERSION", "ANTIGUA (reemplaza lector_facturas.py)"))

datos, nota = lf.leer_archivo(ruta, contenido, usar_ia=False)
print("\nLectura:", nota)
for c in lf.CAMPOS:
    print(f"  {c}: {datos[c]}")
print(f"  servicios: {len(datos['items'])}")

texto = lf.leer_pdf(contenido)
print("\n--- Texto alrededor de 'cuota' / 'venc' (para revisar) ---")
for m in re.finditer(r"cuota|venc", texto, re.IGNORECASE):
    print(repr(texto[max(0, m.start() - 60): m.end() + 80]))
    print()
input("Presiona Enter para cerrar...")
