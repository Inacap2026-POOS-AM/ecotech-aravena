"""Modelos de datos y utilidades de tiempo."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal


def ahora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def antiguedad(obtenido_en):
    """Texto legible: 'hace 2 h 5 min'. Tolerante a fechas corruptas."""
    try:
        t = datetime.fromisoformat(obtenido_en)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "fecha desconocida"
    minutos = max(int((datetime.now(timezone.utc) - t).total_seconds() // 60), 0)
    if minutos < 1:
        return "hace instantes"
    horas, mins = divmod(minutos, 60)
    dias, horas = divmod(horas, 24)
    if dias:
        return f"hace {dias} d {horas} h"
    if horas:
        return f"hace {horas} h {mins} min"
    return f"hace {mins} min"


@dataclass
class Clima:
    ciudad: str
    pais: str
    latitud: float
    longitud: float
    temperatura_c: float
    humedad_pct: float
    estado: str
    obtenido_en: str = field(default_factory=ahora_utc)


@dataclass
class TipoCambio:
    base: str
    moneda: str
    tasa: Decimal
    obtenido_en: str = field(default_factory=ahora_utc)


@dataclass
class Resultado:
    """Envuelve un dato indicando si vino de la API o del Plan B local."""
    dato: object
    origen: str          # "api" | "local"
    aviso: str = ""      # motivo de la degradación (seguro para el usuario)
