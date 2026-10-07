"""Lee facturas de proveedores y saca sus datos y su detalle de servicios.

- XML de SUNAT (UBL 2.1) o ZIP que lo contenga: lectura exacta y gratis.
- PDF o imagen: si hay clave de API (ANTHROPIC_API_KEY), los lee la inteligencia artificial,
  sea cual sea el formato del proveedor. Sin clave, se intenta una lectura por reglas.
"""
import base64
import io
import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime

CAMPOS = ["ruc", "proveedor", "comprobante", "fecha_emision", "fecha_vencimiento",
          "moneda", "subtotal", "igv", "total"]

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def _vacio():
    return {**{c: None for c in CAMPOS}, "items": []}


def _numero(texto):
    if texto is None:
        return None
    t = str(texto).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d{2}", t):  # 1.234,56
        t = t.replace(".", "").replace(",", ".")
    else:                                              # 1,234.56
        t = t.replace(",", "")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def _fecha(texto):
    """Convierte 05/10/2026, 05-10-2026 o 2026-10-05 a AAAA-MM-DD."""
    if not texto:
        return None
    t = texto.strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(t, formato).date().isoformat()
        except ValueError:
            pass
    return None


# ---------- XML (SUNAT) ----------
def leer_xml(contenido):
    raiz = ET.fromstring(contenido)

    def t(ruta):
        el = raiz.find(ruta, NS)
        return el.text.strip() if el is not None and el.text else None

    d = _vacio()
    d["comprobante"] = t("cbc:ID")
    d["fecha_emision"] = _fecha(t("cbc:IssueDate"))
    vencimientos = [el.text.strip() for el in raiz.findall("cac:PaymentTerms/cbc:PaymentDueDate", NS) if el.text]
    d["fecha_vencimiento"] = _fecha(t("cbc:DueDate") or (max(vencimientos) if vencimientos else None))
    d["moneda"] = t("cbc:DocumentCurrencyCode")
    prov = "cac:AccountingSupplierParty/cac:Party/"
    d["ruc"] = (t(prov + "cac:PartyIdentification/cbc:ID")
                or t("cac:AccountingSupplierParty/cbc:CustomerAssignedAccountID"))
    d["proveedor"] = (t(prov + "cac:PartyLegalEntity/cbc:RegistrationName")
                      or t(prov + "cac:PartyName/cbc:Name"))
    d["subtotal"] = _numero(t("cac:LegalMonetaryTotal/cbc:LineExtensionAmount")
                            or t("cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount"))
    d["igv"] = _numero(t("cac:TaxTotal/cbc:TaxAmount"))
    d["total"] = _numero(t("cac:LegalMonetaryTotal/cbc:PayableAmount"))
    for linea in raiz.findall("cac:InvoiceLine", NS):
        def lt(ruta):
            el = linea.find(ruta, NS)
            return el.text.strip() if el is not None and el.text else None
        descripcion = " ".join(el.text.strip() for el in linea.findall("cac:Item/cbc:Description", NS) if el.text)
        d["items"].append({
            "descripcion": descripcion or None,
            "cantidad": _numero(lt("cbc:InvoicedQuantity")),
            "valor_unitario": _numero(lt("cac:Price/cbc:PriceAmount")),
            "importe": _numero(lt("cbc:LineExtensionAmount")),
        })
    return d


# ---------- PDF ----------
RE_COMPROBANTE = re.compile(r"\b([FE][A-Z0-9]{3})\s*[-–]\s*0*(\d{1,8})\b")
RE_RUC = re.compile(r"\b((?:10|15|17|20)\d{9})\b")
RE_FECHA = r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})"
RE_MONTO = r"(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})"
SOCIEDADES = re.compile(r"\b(S\.?A\.?C\.?|S\.?A\.?A\.?|S\.?A\.?|E\.?I\.?R\.?L\.?|S\.?R\.?L\.?)\s*$", re.IGNORECASE)


def _ultimo(patron, texto):
    m = re.findall(patron, texto, re.IGNORECASE)
    return m[-1] if m else None


def parsear_texto(texto):
    d = _vacio()
    m = RE_COMPROBANTE.search(texto)
    if m:
        d["comprobante"] = f"{m.group(1)}-{int(m.group(2)):08d}"
    rucs = RE_RUC.findall(texto)
    if rucs:
        d["ruc"] = rucs[0]  # el emisor va arriba, antes del cliente

    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    for l in lineas[:15]:
        if SOCIEDADES.search(l) and "RUC" not in l.upper():
            d["proveedor"] = l
            break

    em = re.search(r"Fecha\s+de\s+emisi[oó]n\s*:?\s*" + RE_FECHA, texto, re.IGNORECASE)
    ve = re.search(r"(?:Fecha\s+de\s+)?vencimiento\s*:?\s*" + RE_FECHA, texto, re.IGNORECASE)
    d["fecha_emision"] = _fecha(em.group(1)) if em else None
    d["fecha_vencimiento"] = _fecha(ve.group(1)) if ve else None
    if not d["fecha_emision"]:
        fechas = [_fecha(f) for f in re.findall(RE_FECHA, texto)]
        fechas = [f for f in fechas if f]
        if fechas:
            d["fecha_emision"] = fechas[0]

    arriba = texto.upper()
    if "US$" in arriba or "DÓLAR" in arriba or "DOLAR" in arriba or "USD" in arriba:
        d["moneda"] = "USD"
    elif "S/" in arriba or "SOLES" in arriba or "PEN" in arriba:
        d["moneda"] = "PEN"

    d["total"] = _numero(_ultimo(r"(?:importe\s+total|total\s+a\s+pagar|total\s+venta|\btotal\b)"
                                 r"[^\d]{0,30}" + RE_MONTO, texto))
    d["igv"] = _numero(_ultimo(r"\bI\.?G\.?V\.?(?:\s*\(?\s*18\s*%\s*\)?)?[^\d]{0,25}" + RE_MONTO, texto))
    d["subtotal"] = _numero(_ultimo(r"(?:op\.?\s*gravadas?|operaci[oó]n\s+gravada|sub\s*-?\s*total|valor\s+de\s+venta)"
                                    r"[^\d]{0,30}" + RE_MONTO, texto))
    if d["subtotal"] is None and d["total"] is not None and d["igv"] is not None:
        d["subtotal"] = round(d["total"] - d["igv"], 2)
    if d["igv"] is None and d["total"] is not None and d["subtotal"] is not None:
        d["igv"] = round(d["total"] - d["subtotal"], 2)
    return d


def leer_pdf(contenido):
    try:
        import pymupdf
        with pymupdf.open(stream=contenido, filetype="pdf") as doc:
            return "\n".join(doc[i].get_text("text") for i in range(min(3, len(doc))))
    except ImportError:
        from pypdf import PdfReader
        lector = PdfReader(io.BytesIO(contenido))
        return "\n".join((p.extract_text() or "") for p in lector.pages[:3])


# ---------- Detalle de servicios desde el PDF (sin IA) ----------
# En vez de columnas fijas por proveedor, se busca la fila de encabezados de la tabla
# (Código, Cantidad, Descripción, P. Unit., Importe...) y se arman las columnas
# según dónde está cada encabezado en esa factura.
import unicodedata

NUMERO = re.compile(r"-?\(?[\d.,]*\d[\d.,]*\)?")
FIN_TABLA = ("gravad", "sub total", "subtotal", "i.g.v", "igv", "importe total", "total a pagar",
             "son:", "son ", "valor de venta", "total venta", "observacion", "op. exonerad", "op. inafect")


def _sin_tildes(t):
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _clase(frase):
    t = _sin_tildes(frase)
    if any(k in t for k in ("descrip", "detalle", "concepto", "producto", "servicio")):
        return "descripcion"
    if "cant" in t:
        return "cantidad"
    if "unit" in t or t.replace(" ", "") in ("p.u.", "pu", "p/u", "v.u.", "vu"):
        return "unitario"
    if "precio" in t:
        return "precio"
    if any(k in t for k in ("importe", "total", "valor", "monto", "sub-total")):
        return "importe"
    if "cod" in t:
        return "codigo"
    if t.strip(". ") in ("um", "u.m", "und", "unid", "unidad", "medida", "u. medida", "unidad de medida"):
        return "um"
    if t.strip(". ") in ("item", "n", "no", "nro", "n°", "#", "n.°"):
        return "item"
    return None


def _lineas(palabras, tolerancia=3):
    filas = []
    for w in sorted(palabras, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        y = (w[1] + w[3]) / 2
        for f in filas:
            if abs(f["y"] - y) <= tolerancia:
                f["w"].append(w)
                break
        else:
            filas.append({"y": y, "w": [w]})
    for f in filas:
        f["w"].sort(key=lambda w: w[0])
        f["texto"] = " ".join(w[4] for w in f["w"])
    return filas


def _frases(palabras, separacion=6):
    """Agrupa las palabras de una línea en frases (una por columna) según la distancia entre ellas."""
    frases = []
    for w in sorted(palabras, key=lambda w: w[0]):
        if frases and w[0] - frases[-1]["x1"] <= separacion:
            frases[-1]["texto"] += " " + w[4]
            frases[-1]["x1"] = w[2]
        else:
            frases.append({"texto": w[4], "x0": w[0], "x1": w[2]})
    return frases


def _encabezado(lineas):
    """Devuelve (índice de la última línea del encabezado, columnas) o None."""
    for i, linea in enumerate(lineas):
        frases = _frases(linea["w"])
        clases = [_clase(f["texto"]) for f in frases]
        if "descripcion" not in clases or not ({"cantidad", "unitario", "precio", "importe"} & set(clases)):
            continue
        fin = i
        # encabezados partidos en dos líneas ("Valor Venta / Unitario")
        if i + 1 < len(lineas) and lineas[i + 1]["y"] - linea["y"] <= 14 \
                and not any(NUMERO.fullmatch(w[4]) for w in lineas[i + 1]["w"]):
            for w in lineas[i + 1]["w"]:
                centro = (w[0] + w[2]) / 2
                destino = next((f for f in frases if f["x0"] - 6 <= centro <= f["x1"] + 6), None)
                if destino:
                    destino["texto"] += " " + w[4]
                    destino["x1"] = max(destino["x1"], w[2])
                else:
                    frases.append({"texto": w[4], "x0": w[0], "x1": w[2]})
            fin = i + 1
        columnas = sorted(({**f, "clase": _clase(f["texto"]), "centro": (f["x0"] + f["x1"]) / 2} for f in frases),
                          key=lambda c: c["x0"])
        return fin, columnas
    return None


def _columna_numero(columnas, w):
    centro = (w[0] + w[2]) / 2
    return min(columnas, key=lambda c: abs(c["centro"] - centro))


def _columna_texto(columnas, w):
    elegida = columnas[0]
    for c in columnas:
        if w[0] >= c["x0"] - 6:
            elegida = c
    return elegida


def leer_items_pdf(contenido):
    import pymupdf
    items = []
    with pymupdf.open(stream=contenido, filetype="pdf") as doc:
        for pagina in doc:
            lineas = _lineas(pagina.get_text("words"))
            hallado = _encabezado(lineas)
            if not hallado:
                continue
            fin, columnas = hallado
            hay_ancla = any(c["clase"] in ("codigo", "cantidad", "item") for c in columnas)
            y_anterior = lineas[fin]["y"]
            for linea in lineas[fin + 1:]:
                if linea["y"] - y_anterior > 60:
                    break
                celdas = {}
                for w in linea["w"]:
                    es_numero = bool(NUMERO.fullmatch(w[4]))
                    col = _columna_numero(columnas, w) if es_numero else _columna_texto(columnas, w)
                    if col["clase"] == "descripcion" or not es_numero:
                        clase = col["clase"] if not es_numero or col["clase"] != "descripcion" else "descripcion"
                    else:
                        clase = col["clase"]
                    celdas.setdefault(clase or "otro", []).append(w[4])
                texto = _sin_tildes(linea["texto"])
                tiene_ancla = any(celdas.get(k) for k in ("codigo", "cantidad", "item"))
                # Los totales ("Op. Gravada", "IGV", "Importe total", "SON:") marcan el fin de la tabla.
                if any(k in texto for k in FIN_TABLA) and not (celdas.get("codigo") or celdas.get("item")):
                    break
                y_anterior = linea["y"]
                descripcion = " ".join(celdas.get("descripcion", []))
                importe = _numero(" ".join(celdas.get("importe", [])) or None)
                nueva = tiene_ancla if hay_ancla else importe is not None
                if nueva:
                    unitario = _numero(" ".join(celdas.get("unitario", [])) or None)
                    if unitario is None:
                        unitario = _numero(" ".join(celdas.get("precio", [])) or None)
                    cantidad = _numero(" ".join(celdas.get("cantidad", [])) or None)
                    if importe is None and cantidad and unitario:
                        importe = round(cantidad * unitario, 2)
                    items.append({"descripcion": descripcion or None, "cantidad": cantidad,
                                  "valor_unitario": unitario, "importe": importe})
                elif descripcion and items:  # descripción que continúa en la línea siguiente
                    items[-1]["descripcion"] = ((items[-1]["descripcion"] or "") + " " + descripcion).strip()
    return [it for it in items if it["descripcion"] and (it["importe"] or it["cantidad"] or it["valor_unitario"])]


# ---------- Lectura con inteligencia artificial ----------
API_URL = "https://api.anthropic.com/v1/messages"
MODELO = "claude-haiku-4-5-20251001"  # el más económico; lee PDF e imágenes
TIPOS_IMAGEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

_NUM = {"type": ["number", "null"]}
_TXT = {"type": ["string", "null"]}
ESQUEMA_IA = {
    "type": "object",
    "properties": {
        "ruc": {**_TXT, "description": "RUC del EMISOR (proveedor), 11 dígitos"},
        "proveedor": {**_TXT, "description": "Razón social del emisor"},
        "comprobante": {**_TXT, "description": "Serie y número, p. ej. F001-00000123"},
        "fecha_emision": {**_TXT, "description": "AAAA-MM-DD"},
        "fecha_vencimiento": {**_TXT, "description": "AAAA-MM-DD; si es a crédito en cuotas, la última cuota"},
        "moneda": {"type": ["string", "null"], "enum": ["PEN", "USD", None]},
        "subtotal": {**_NUM, "description": "Valor de venta / operación gravada, sin IGV"},
        "igv": _NUM,
        "total": {**_NUM, "description": "Importe total a pagar"},
        "items": {
            "type": "array",
            "description": "Cada línea del detalle de la factura",
            "items": {
                "type": "object",
                "properties": {
                    "descripcion": _TXT,
                    "cantidad": _NUM,
                    "valor_unitario": {**_NUM, "description": "Sin IGV si la factura lo muestra así"},
                    "importe": {**_NUM, "description": "Importe de la línea, sin IGV si la factura lo muestra así"},
                },
                "required": ["descripcion", "cantidad", "valor_unitario", "importe"],
            },
        },
    },
    "required": CAMPOS + ["items"],
}

INSTRUCCIONES = (
    "Esta es una factura electrónica peruana que un proveedor emitió a nuestra empresa. "
    "Registra sus datos con la herramienta. Los datos de RUC y razón social son los del EMISOR (quien vende), "
    "no los del cliente. Fechas en formato AAAA-MM-DD. Montos como números, sin símbolos ni separadores de miles. "
    "Moneda: PEN para soles, USD para dólares. Si un dato no aparece en la factura, déjalo en null; no lo inventes."
)


def clave_api():
    """Busca ANTHROPIC_API_KEY en el entorno, en .streamlit/secrets.toml o en los Secrets de Streamlit."""
    clave = os.environ.get("ANTHROPIC_API_KEY")
    archivo = Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if not clave and archivo.exists():
        try:
            with open(archivo, "rb") as f:
                clave = tomllib.load(f).get("ANTHROPIC_API_KEY")
        except tomllib.TOMLDecodeError:
            clave = None
    if not clave:
        try:
            import streamlit as st
            clave = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            clave = None
    return (clave or "").strip() or None


def leer_con_ia(nombre, contenido, clave):
    extension = Path(nombre.lower()).suffix
    datos64 = base64.standard_b64encode(contenido).decode("ascii")
    if extension == ".pdf":
        bloque = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": datos64}}
    else:
        bloque = {"type": "image", "source": {"type": "base64", "media_type": TIPOS_IMAGEN[extension], "data": datos64}}
    cuerpo = {
        "model": MODELO,
        "max_tokens": 2000,
        "tools": [{"name": "registrar_factura", "description": "Registra los datos de la factura",
                   "input_schema": ESQUEMA_IA}],
        "tool_choice": {"type": "tool", "name": "registrar_factura"},
        "messages": [{"role": "user", "content": [bloque, {"type": "text", "text": INSTRUCCIONES}]}],
    }
    pedido = urllib.request.Request(
        API_URL, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=120) as r:
        respuesta = json.load(r)
    entrada = next(b["input"] for b in respuesta["content"] if b.get("type") == "tool_use")

    d = _vacio()
    for c in ("ruc", "proveedor", "comprobante"):
        d[c] = (str(entrada.get(c)).strip() or None) if entrada.get(c) else None
    d["fecha_emision"] = _fecha(entrada.get("fecha_emision"))
    d["fecha_vencimiento"] = _fecha(entrada.get("fecha_vencimiento"))
    moneda = (entrada.get("moneda") or "").upper()
    d["moneda"] = moneda if moneda in ("PEN", "USD") else None
    for c in ("subtotal", "igv", "total"):
        d[c] = _numero(entrada.get(c))
    for it in entrada.get("items") or []:
        d["items"].append({
            "descripcion": (str(it.get("descripcion")).strip() if it.get("descripcion") else None),
            "cantidad": _numero(it.get("cantidad")),
            "valor_unitario": _numero(it.get("valor_unitario")),
            "importe": _numero(it.get("importe")),
        })
    return d


def _error_api(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            detalle = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            detalle = ""
        if e.code == 401:
            return "la clave de API no es válida"
        if "credit" in detalle.lower() or "balance" in detalle.lower():
            return "no hay saldo en la cuenta de la API"
        return f"error {e.code} de la API"
    return "no se pudo conectar con la API"


# ---------- Entrada única ----------
def leer_archivo(nombre, contenido, usar_ia=True):
    """Devuelve (datos, nota). 'nota' explica qué tan confiable es la lectura."""
    n = nombre.lower()
    clave = clave_api() if usar_ia else None
    if clave and (n.endswith(".pdf") or Path(n).suffix in TIPOS_IMAGEN):
        try:
            return leer_con_ia(nombre, contenido, clave), "Leída con IA: revisa antes de guardar"
        except Exception as e:  # si falla, se intenta la lectura por reglas
            motivo = _error_api(e)
            if not n.endswith(".pdf"):
                return _vacio(), f"No se pudo leer con IA ({motivo}). Complétala a mano"
            datos, nota = leer_archivo(nombre, contenido, usar_ia=False)
            return datos, f"IA no disponible ({motivo}). {nota}"
    if Path(n).suffix in TIPOS_IMAGEN:
        return _vacio(), "Imagen: para leerla se necesita la clave de IA. Complétala a mano"
    try:
        if n.endswith(".xml"):
            return leer_xml(contenido), "Leída del XML (exacta)"
        if n.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                xmls = [x for x in z.namelist() if x.lower().endswith(".xml")]
                if xmls:
                    return leer_xml(z.read(xmls[0])), "Leída del XML dentro del ZIP (exacta)"
                pdfs = [x for x in z.namelist() if x.lower().endswith(".pdf")]
                if pdfs:
                    return leer_archivo(pdfs[0], z.read(pdfs[0]))
            return _vacio(), "El ZIP no tiene XML ni PDF"
        if n.endswith(".pdf"):
            texto = leer_pdf(contenido)
            if len(texto.strip()) < 30:
                return _vacio(), "PDF escaneado: no se pudo leer, complétala a mano"
            datos = parsear_texto(texto)
            try:
                datos["items"] = leer_items_pdf(contenido)
            except Exception:
                datos["items"] = []
            faltan = [c for c in ("comprobante", "ruc", "total", "fecha_emision") if not datos[c]]
            nota = "Leída del PDF: revisa los datos"
            if faltan:
                nota += " (faltan: " + ", ".join(faltan) + ")"
            return datos, nota
    except Exception as e:  # archivo dañado o formato inesperado
        return _vacio(), f"No se pudo leer ({type(e).__name__})"
    return _vacio(), "Formato no soportado"
