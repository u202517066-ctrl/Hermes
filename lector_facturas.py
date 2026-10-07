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
    d["igv"] = _numero(_ultimo(r"\bI\.?G\.?V\.?\b[^\d\n]{0,25}(?:18\s*%[^\d\n]{0,15})?" + RE_MONTO, texto))
    d["subtotal"] = _numero(_ultimo(r"(?:op\.?\s*gravadas?|operaci[oó]n\s+gravada|sub\s*-?\s*total|valor\s+de\s+venta)"
                                    r"[^\d]{0,30}" + RE_MONTO, texto))
    if d["subtotal"] is None and d["total"] is not None and d["igv"] is not None:
        d["subtotal"] = round(d["total"] - d["igv"], 2)
    return d


def leer_pdf(contenido):
    from pypdf import PdfReader
    lector = PdfReader(io.BytesIO(contenido))
    texto = "\n".join((p.extract_text() or "") for p in lector.pages[:3])
    return texto


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
            faltan = [c for c in ("comprobante", "ruc", "total", "fecha_emision") if not datos[c]]
            nota = "Leída del PDF: revisa los datos"
            if faltan:
                nota += " (faltan: " + ", ".join(faltan) + ")"
            return datos, nota
    except Exception as e:  # archivo dañado o formato inesperado
        return _vacio(), f"No se pudo leer ({type(e).__name__})"
    return _vacio(), "Formato no soportado"
