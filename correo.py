"""Envío de correos de HERMES por SMTP (por defecto, Outlook / Microsoft 365).

Datos que se ponen en .streamlit/secrets.toml (en tu PC) y en Secrets de Streamlit Cloud:
    SMTP_USUARIO = "tucorreo@empresa.com"
    SMTP_CLAVE = "contraseña o contraseña de aplicación"
    CORREO_DESTINO = "tucorreo@empresa.com"      # opcional: a quién llega por defecto
    SMTP_SERVIDOR = "smtp.office365.com"         # opcional
    SMTP_PUERTO = 587                            # opcional
"""
import os
import smtplib
import tomllib
from email.message import EmailMessage
from pathlib import Path

CARPETA = Path(__file__).resolve().parent


def _config():
    datos = {}
    archivo = CARPETA / ".streamlit" / "secrets.toml"
    if archivo.exists():
        try:
            with open(archivo, "rb") as f:
                datos = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            datos = {}
    if not datos.get("SMTP_USUARIO"):
        try:
            import streamlit as st
            datos = {k: st.secrets[k] for k in st.secrets.keys()}
        except Exception:
            pass

    def valor(clave, defecto=None):
        return os.environ.get(clave) or datos.get(clave) or defecto

    return {
        "usuario": valor("SMTP_USUARIO"),
        "clave": valor("SMTP_CLAVE"),
        "servidor": valor("SMTP_SERVIDOR", "smtp.office365.com"),
        "puerto": int(valor("SMTP_PUERTO", 587)),
        "destino": valor("CORREO_DESTINO") or valor("SMTP_USUARIO"),
    }


def configurado():
    c = _config()
    return bool(c["usuario"] and c["clave"])


def destino_por_defecto():
    return _config()["destino"] or ""


def enviar(destinos, asunto, html, adjuntos=()):
    """Envía un correo en HTML. 'adjuntos' es una lista de (nombre, bytes, tipo_mime).
    Devuelve None si salió bien, o un mensaje de error entendible."""
    c = _config()
    if not (c["usuario"] and c["clave"]):
        return "Falta configurar SMTP_USUARIO y SMTP_CLAVE en los secrets."
    destinos = [d.strip() for d in (destinos if isinstance(destinos, (list, tuple)) else destinos.split(",")) if d.strip()]
    if not destinos:
        return "Escribe al menos un correo de destino."

    msg = EmailMessage()
    msg["From"] = c["usuario"]
    msg["To"] = ", ".join(destinos)
    msg["Subject"] = asunto
    msg.set_content("Este correo tiene formato HTML. Si no lo ves bien, revisa el archivo adjunto.")
    msg.add_alternative(html, subtype="html")
    for nombre, contenido, tipo in adjuntos:
        principal, secundario = tipo.split("/", 1)
        msg.add_attachment(contenido, maintype=principal, subtype=secundario, filename=nombre)

    try:
        with smtplib.SMTP(c["servidor"], c["puerto"], timeout=30) as smtp:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls()
                smtp.ehlo()
            smtp.login(c["usuario"], c["clave"])
            smtp.send_message(msg)
        return None
    except smtplib.SMTPAuthenticationError as e:
        detalle = str(e).lower()
        if "smtpclientauthentication is disabled" in detalle or "5.7.139" in detalle or "basic authentication" in detalle:
            return ("Microsoft 365 tiene desactivado el envío SMTP para esta cuenta. Pide a TI que habilite "
                    "«SMTP autenticado» (Authenticated SMTP) para el buzón, o que te dé una contraseña de aplicación.")
        return "El usuario o la contraseña del correo no son correctos (o la cuenta pide doble factor: usa una contraseña de aplicación)."
    except (smtplib.SMTPException, OSError) as e:
        return f"No se pudo enviar el correo: {type(e).__name__}. Revisa el servidor y el puerto, o la conexión."
