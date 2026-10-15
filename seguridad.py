import hashlib
import hmac
import os
import re
import unicodedata

import db


ROLES = ["colaborador", "jefe", "admin", "aprobador_facturas"]
PRIORIDAD = ["admin", "jefe", "colaborador", "aprobador_facturas"]  # el primero que tenga es su rol principal


def roles_de(texto):
    """'jefe,aprobador_facturas' -> ['jefe', 'aprobador_facturas'] (en el orden de ROLES)."""
    marcados = {r.strip() for r in str(texto or "").split(",") if r.strip()}
    return [r for r in ROLES if r in marcados] or ["colaborador"]


def texto_roles(roles):
    roles = [r for r in ROLES if r in set(roles)]
    return ",".join(roles) or "colaborador"


def rol_principal(roles):
    return next((r for r in PRIORIDAD if r in set(roles)), "colaborador")


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
            "rol": texto_roles(rol if isinstance(rol, (list, tuple, set)) else roles_de(rol)), "cod": cod,
            "nombre": nombre, "apellido": apellido, "estado": estado,
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
        {"rol": texto_roles(rol if isinstance(rol, (list, tuple, set)) else roles_de(rol)), "cod": cod,
         "estado": estado, "usuario": usuario},
    )


# ---------- Mantener la sesión iniciada ----------
DIAS_SESION = 14


def _huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def crear_sesion(usuario):
    """Crea una llave temporal para recordar el ingreso en este navegador. Devuelve la llave (solo se guarda su huella)."""
    import secrets
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    expira = (db.hoy() + timedelta(days=DIAS_SESION)).isoformat()
    db.ejecutar("DELETE FROM sesiones WHERE expira < :h", {"h": db.hoy().isoformat()})
    db.ejecutar("INSERT INTO sesiones (token, usuario, expira, creado) VALUES (:t, :u, :e, :c)",
                {"t": _huella(token), "u": usuario, "e": expira, "c": db.ahora()})
    return token


def usuario_de_sesion(token):
    """Devuelve los datos de ingreso si la llave es válida y el usuario sigue activo; si no, None."""
    if not token:
        return None
    fila = db.uno("SELECT usuario FROM sesiones WHERE token = :t AND expira >= :h",
                  {"t": _huella(token), "h": db.hoy().isoformat()})
    if not fila:
        return None
    u = datos_usuario(fila.usuario)
    if not u or u["estado"] != "ACTIVO":
        return None
    return {"usuario": u["usuario"], "rol": u["rol"], "cod": u["cod"]}


def cerrar_sesion(token=None, usuario=None):
    """Invalida una llave, o todas las de un usuario."""
    if token:
        db.ejecutar("DELETE FROM sesiones WHERE token = :t", {"t": _huella(token)})
    if usuario:
        db.ejecutar("DELETE FROM sesiones WHERE usuario = :u", {"u": usuario})


def cambiar_clave(usuario, clave):
    cerrar_sesion(usuario=usuario)  # al cambiar la contraseña se cierran las sesiones recordadas
    sal = os.urandom(16).hex()
    db.ejecutar(
        "UPDATE usuarios SET sal = :sal, clave = :clave WHERE usuario = :usuario",
        {"sal": sal, "clave": _hash(clave, sal), "usuario": usuario},
    )


def eliminar_usuario(usuario):
    cerrar_sesion(usuario=usuario)
    db.ejecutar("DELETE FROM usuarios WHERE usuario = :u", {"u": usuario})
