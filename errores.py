"""Jerarquía de excepciones del proyecto.

Los mensajes de estas excepciones son SEGUROS para mostrar al usuario:
nunca incluyen URLs con parámetros, llaves, rutas internas ni trazas.
El detalle técnico va únicamente al log (ecotech.log).
"""


class ErrorValidacion(ValueError):
    """La entrada del usuario no cumple el formato esperado."""


class ErrorAutenticacion(Exception):
    """Credenciales inválidas o sesión no iniciada/expirada."""


class ErrorApi(Exception):
    """Error controlado al consumir un servicio externo."""


class ErrorSolicitud(ErrorApi):
    """Respuesta 4xx: la solicitud es incorrecta; reintentar no sirve."""


class ErrorDisponibilidad(ErrorApi):
    """Red caída, timeout o 5xx/429 persistente tras agotar los reintentos."""


class ErrorDatos(ErrorApi):
    """La API respondió, pero el contenido no tiene el formato esperado."""


class ErrorSinDatos(ErrorApi):
    """La API falló y tampoco existen datos locales para el Plan B."""
