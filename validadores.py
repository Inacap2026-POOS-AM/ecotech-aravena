"""Validación y saneamiento de TODA entrada del usuario (lista blanca)."""
import re
from decimal import Decimal, InvalidOperation

from errores import ErrorValidacion

_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# Letras (con tildes/ñ), separadas por un espacio, apóstrofe o guion. Sin dígitos ni símbolos.
_CIUDAD = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$", re.UNICODE)
_PAIS = re.compile(r"^[A-Za-z]{2}$")
_MONEDA = re.compile(r"^[A-Za-z]{3}$")
_USUARIO = re.compile(r"^[A-Za-z0-9_.\-]{3,32}$")

MAX_PASSWORD_BYTES = 72  # límite real de bcrypt
MONTO_MAX = Decimal("1000000")


def _limpiar(texto):
    if not isinstance(texto, str):
        raise ErrorValidacion("Entrada inválida.")
    return _CTRL.sub("", texto).strip()


def validar_ciudad(texto):
    t = " ".join(_limpiar(texto).split())
    if not t:
        raise ErrorValidacion("La ciudad no puede estar vacía.")
    if len(t) > 60 or not _CIUDAD.match(t):
        raise ErrorValidacion("Ciudad inválida: usa solo letras, espacios o guiones (máx. 60).")
    return t.title()


def validar_pais(texto):
    t = _limpiar(texto)
    if not _PAIS.match(t):
        raise ErrorValidacion("País inválido: usa el código de 2 letras (ej.: CL, AR, BR).")
    return t.upper()


def validar_moneda(texto):
    t = _limpiar(texto)
    if not _MONEDA.match(t):
        raise ErrorValidacion("Moneda inválida: usa el código de 3 letras (ej.: CLP, EUR, BRL).")
    return t.upper()


def validar_monto(texto):
    t = _limpiar(texto).replace(",", ".")
    try:
        monto = Decimal(t)
    except InvalidOperation:
        raise ErrorValidacion("Monto inválido: ingresa un número (ej.: 1500.50).") from None
    if not monto.is_finite() or monto <= 0 or monto > MONTO_MAX:
        raise ErrorValidacion("El monto debe ser mayor que 0 y no superar 1.000.000 USD.")
    return monto


def validar_usuario(texto):
    t = _limpiar(texto)
    if not _USUARIO.match(t):
        raise ErrorValidacion("Usuario inválido: 3 a 32 caracteres (letras, números, . _ -).")
    return t


def validar_password_login(texto):
    """En el login solo exigimos no vacío y largo razonable (evita abuso del hash)."""
    if not isinstance(texto, str) or not texto:
        raise ErrorValidacion("La contraseña no puede estar vacía.")
    if len(texto.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ErrorValidacion("Contraseña demasiado larga.")
    return texto


def validar_password_nueva(texto):
    p = validar_password_login(texto)
    if len(p) < 8:
        raise ErrorValidacion("La contraseña debe tener al menos 8 caracteres.")
    if not (any(c.isalpha() for c in p) and any(c.isdigit() for c in p)):
        raise ErrorValidacion("La contraseña debe combinar letras y números.")
    return p
