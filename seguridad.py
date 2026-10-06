import hashlib
import hmac
import os
import re
import unicodedata

import db


def crear_tabla():
    db.crear_tablas()


def _hash(clave, sal):
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), 200_000).hex()


def crear_usuario(usuario, clave, rol, cod=None, nombre=None, apellido=None, estado="ACTIVO"):
    sal = os.urandom(16).hex()
    db.ejecutar(
        "INSERT INTO usuarios (usuario, sal, clave, rol, cod, nombre, apellido, estado) "
        "VALUES (:usuario, :sal, :clave, :rol, :cod, :nombre, :apellido, :estado)",
        {
            "usuario": usuario.strip().lower(), "sal": sal, "clave": _hash(clave, sal),
            "rol": rol, "cod": cod, "nombre": nombre, "apellido": apellido, "estado": estado,
        },
    )


def datos_usuario(usuario):
    fila = db.uno(
        "SELECT usuario, rol, cod, estado, nombre, apellido FROM usuarios WHERE usuario = :u",
        {"u": usuario},
    )
    return dict(fila._mapping) if fila else None


def verificar(usuario, clave):
    fila = db.uno(
        "SELECT usuario, sal, clave, rol, cod, estado FROM usuarios WHERE usuario = :u",
        {"u": usuario.strip().lower()},
    )
    if fila and hmac.compare_digest(_hash(clave, fila.sal), fila.clave):
        if fila.estado != "ACTIVO":
            return {"error": "Tu cuenta está pendiente de aprobación del administrador."}
        return {"usuario": fila.usuario, "rol": fila.rol, "cod": fila.cod}
    return None


def _tokens(texto):
    t = unicodedata.normalize("NFD", str(texto))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").upper()
    return set(re.findall(r"[A-Z]+", t))


def buscar_persona(nombre, apellido):
    """Devuelve el cod si hay una única coincidencia en rrhh_personal."""
    tn, ta = _tokens(nombre), _tokens(apellido)
    if not tn or not ta:
        return None
    filas = db.consultar("SELECT cod, nombre FROM rrhh_personal")
    coincidencias = []
    for cod, completo in filas.itertuples(index=False):
        ap, _, nom = str(completo).partition(",")
        if ta <= _tokens(ap) and tn <= _tokens(nom):
            coincidencias.append(cod)
    return coincidencias[0] if len(coincidencias) == 1 else None


def registrar(nombre, apellido, correo, clave):
    """Devuelve None si todo salió bien, o el mensaje de error."""
    correo = correo.strip().lower()
    if not nombre.strip() or not apellido.strip():
        return "Completa tu nombre y apellido."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo):
        return "Escribe un correo válido."
    if db.uno("SELECT 1 FROM usuarios WHERE usuario = :u", {"u": correo}):
        return "Ese correo ya está registrado."
    cod = buscar_persona(nombre, apellido)
    if cod and db.uno("SELECT 1 FROM usuarios WHERE cod = :c", {"c": cod}):
        cod = None
    try:
        crear_usuario(correo, clave, "colaborador", cod, nombre.strip(), apellido.strip(), "PENDIENTE")
    except db.IntegrityError:
        return "Ese correo ya está registrado."
    return None


def actualizar_usuario(usuario, rol, cod, estado="ACTIVO"):
    db.ejecutar(
        "UPDATE usuarios SET rol = :rol, cod = :cod, estado = :estado WHERE usuario = :usuario",
        {"rol": rol, "cod": cod, "estado": estado, "usuario": usuario},
    )


def cambiar_clave(usuario, clave):
    sal = os.urandom(16).hex()
    db.ejecutar(
        "UPDATE usuarios SET sal = :sal, clave = :clave WHERE usuario = :usuario",
        {"sal": sal, "clave": _hash(clave, sal), "usuario": usuario},
    )


def eliminar_usuario(usuario):
    db.ejecutar("DELETE FROM usuarios WHERE usuario = :u", {"u": usuario})
