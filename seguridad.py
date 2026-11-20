"""Autenticación: hash con salt (bcrypt) y control de sesión."""
import logging
import time

import bcrypt

from errores import ErrorAutenticacion, ErrorValidacion
from validadores import (validar_password_login, validar_password_nueva,
                         validar_usuario)

log = logging.getLogger("ecotech.seguridad")

_DUMMY_HASH = None


def hashear_password(password):
    """bcrypt genera un salt aleatorio por contraseña y lo incrusta en el hash."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verificar_password(password, hash_guardado):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("ascii"))
    except (ValueError, TypeError, AttributeError):
        return False


def _hash_señuelo():
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hashear_password("senuelo-no-es-una-clave-real-0")
    return _DUMMY_HASH


def registrar_usuario(db, usuario, password):
    usuario = validar_usuario(usuario)
    password = validar_password_nueva(password)
    if not db.crear_usuario(usuario, hashear_password(password)):
        raise ErrorValidacion("Ese nombre de usuario ya existe.")
    log.info("Usuario registrado: %s", usuario)


def autenticar(db, usuario, password):
    """Devuelve el usuario o lanza ErrorAutenticacion con mensaje genérico.

    Si el usuario no existe igual se verifica contra un hash señuelo, para que
    el tiempo de respuesta no revele qué usuarios existen.
    """
    usuario = validar_usuario(usuario)
    password = validar_password_login(password)
    hash_guardado = db.obtener_hash(usuario)
    ok = verificar_password(password, hash_guardado or _hash_señuelo())
    if not (hash_guardado and ok):
        log.warning("Login fallido para usuario=%s", usuario)
        raise ErrorAutenticacion("Credenciales inválidas.")
    log.info("Login correcto: %s", usuario)
    return usuario


class Sesion:
    """Estado de sesión. Los servicios la exigen: sin sesión válida NO hay consumo de APIs."""

    def __init__(self, ttl_segundos=900, reloj=time.monotonic):
        self._usuario = None
        self._expira = 0.0
        self._ttl = ttl_segundos
        self._reloj = reloj

    def iniciar(self, usuario):
        self._usuario = usuario
        self._expira = self._reloj() + self._ttl

    def cerrar(self):
        self._usuario = None
        self._expira = 0.0

    @property
    def usuario(self):
        return self._usuario

    def exigir(self):
        """Lanza ErrorAutenticacion si no hay sesión o expiró; renueva si es válida."""
        if self._usuario is None or self._reloj() >= self._expira:
            self.cerrar()
            raise ErrorAutenticacion("Sesión no iniciada o expirada. Inicia sesión nuevamente.")
        self._expira = self._reloj() + self._ttl
        return self._usuario
