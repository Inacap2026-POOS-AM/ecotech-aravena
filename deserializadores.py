"""Clases deserializadoras: validan el JSON externo y lo convierten a modelos propios.

Principio: no confiar en la API. Se verifica estructura, tipos, rangos y coherencia
antes de que el dato llegue a la lógica del sistema o a la base de datos.
"""
import math
from dataclasses import dataclass
from decimal import Decimal

from errores import ErrorDatos
from modelos import Clima, TipoCambio


def _numero(valor, nombre, minimo, maximo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ErrorDatos(f"El servicio entregó un valor no numérico en '{nombre}'.")
    if not (minimo <= valor <= maximo):
        raise ErrorDatos(f"El servicio entregó un valor fuera de rango en '{nombre}'.")
    return float(valor)


def _dict(valor, nombre):
    if not isinstance(valor, dict):
        raise ErrorDatos(f"Respuesta del servicio sin la estructura esperada ('{nombre}').")
    return valor


# Códigos meteorológicos WMO (Open-Meteo) -> texto
def descripcion_wmo(codigo):
    c = int(codigo)
    if c == 0:
        return "Despejado"
    if c in (1, 2):
        return "Parcialmente nublado"
    if c == 3:
        return "Nublado"
    if c in (45, 48):
        return "Niebla"
    if 51 <= c <= 57:
        return "Llovizna"
    if 61 <= c <= 67:
        return "Lluvia"
    if 71 <= c <= 77:
        return "Nieve"
    if 80 <= c <= 82:
        return "Chubascos"
    if c in (85, 86):
        return "Chubascos de nieve"
    if c >= 95:
        return "Tormenta"
    return "Condición no clasificada"


@dataclass
class Lugar:
    latitud: float
    longitud: float


class ClimaDeserializador:
    @staticmethod
    def lugar(json_geo, pais):
        """Elige de la geocodificación el primer resultado del país pedido."""
        datos = _dict(json_geo, "geocodificación")
        resultados = datos.get("results")
        if not isinstance(resultados, list) or not resultados:
            raise ErrorDatos("No se encontró la ciudad indicada.")
        for r in resultados:
            if isinstance(r, dict) and str(r.get("country_code", "")).upper() == pais:
                return Lugar(_numero(r.get("latitude"), "latitud", -90, 90),
                             _numero(r.get("longitude"), "longitud", -180, 180))
        raise ErrorDatos("No se encontró la ciudad en el país indicado.")

    @staticmethod
    def clima(json_pron, ciudad, pais, lugar):
        actual = _dict(_dict(json_pron, "pronóstico").get("current"), "current")
        return Clima(
            ciudad=ciudad,
            pais=pais,
            latitud=lugar.latitud,
            longitud=lugar.longitud,
            temperatura_c=_numero(actual.get("temperature_2m"), "temperatura", -90, 60),
            humedad_pct=_numero(actual.get("relative_humidity_2m"), "humedad", 0, 100),
            estado=descripcion_wmo(_numero(actual.get("weather_code"), "estado", 0, 99)),
        )


class TipoCambioDeserializador:
    @staticmethod
    def tasa(json_cambio, base, moneda):
        datos = _dict(json_cambio, "tipo de cambio")
        if datos.get("result") != "success":
            raise ErrorDatos("El servicio de tipo de cambio no entregó un resultado válido.")
        if str(datos.get("base_code", "")).upper() != base:
            raise ErrorDatos("El servicio entregó una moneda base distinta a la esperada.")
        tasas = _dict(datos.get("rates"), "rates")
        if moneda not in tasas:
            raise ErrorDatos(f"La moneda {moneda} no está disponible en el servicio.")
        valor = _numero(tasas[moneda], "tasa", 0, 1e12)
        if valor <= 0:
            raise ErrorDatos("El servicio entregó una tasa no válida.")
        return TipoCambio(base=base, moneda=moneda, tasa=Decimal(str(valor)))
