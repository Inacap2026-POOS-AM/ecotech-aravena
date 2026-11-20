"""Casos de uso: consumen la API, persisten y aplican el Plan B (degradación controlada).

Todas las funciones exigen una Sesion válida: la barrera de autenticación vive en
esta capa, no solo en el menú, así que no se puede consumir una API saltándose el login.
"""
import logging
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal

import config
from deserializadores import ClimaDeserializador, TipoCambioDeserializador
from errores import ErrorApi, ErrorSinDatos
from modelos import ahora_utc, Resultado
from validadores import validar_ciudad, validar_moneda, validar_pais

log = logging.getLogger("ecotech.servicios")


def obtener_clima(sesion, ciudad, pais, cliente, db):
    sesion.exigir()
    ciudad, pais = validar_ciudad(ciudad), validar_pais(pais)
    try:
        geo = cliente.get_json(config.GEOCODING_URL, {
            "name": ciudad, "count": 10, "language": "es", "format": "json"})
        lugar = ClimaDeserializador.lugar(geo, pais)
        pron = cliente.get_json(config.PRONOSTICO_URL, {
            "latitude": lugar.latitud, "longitude": lugar.longitud,
            "current": "temperature_2m,relative_humidity_2m,weather_code",
            "timezone": "auto"})
        clima = ClimaDeserializador.clima(pron, ciudad, pais, lugar)
        clima = replace(clima, obtenido_en=ahora_utc())
    except ErrorApi as exc:
        log.warning("Clima: API no disponible (%s). Se intenta Plan B.", type(exc).__name__)
        local = db.obtener_clima(ciudad, pais)
        if local is None:
            raise ErrorSinDatos(f"{exc} Además, no hay datos locales guardados para "
                                f"{ciudad} ({pais}).") from exc
        return Resultado(local, "local", str(exc))
    db.guardar_clima(clima)
    return Resultado(clima, "api")


def obtener_tasa(sesion, moneda, cliente, db):
    sesion.exigir()
    moneda = validar_moneda(moneda)
    base = config.MONEDA_BASE
    try:
        json_cambio = cliente.get_json(config.CAMBIO_URL)
        tasa = TipoCambioDeserializador.tasa(json_cambio, base, moneda)
        tasa = replace(tasa, obtenido_en=ahora_utc())
    except ErrorApi as exc:
        log.warning("Cambio: API no disponible (%s). Se intenta Plan B.", type(exc).__name__)
        local = db.obtener_tasa(base, moneda)
        if local is None:
            raise ErrorSinDatos(f"{exc} Además, no hay una tasa local guardada para "
                                f"{moneda}.") from exc
        return Resultado(local, "local", str(exc))
    db.guardar_tasa(tasa)
    return Resultado(tasa, "api")


def calcular_pago(monto_usd, tasa):
    """Pago en moneda local = monto USD x tasa. Decimal para no acumular error de punto flotante."""
    return (Decimal(monto_usd) * Decimal(tasa)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
