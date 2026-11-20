"""Configuración centralizada. Los secretos viven en .env (fuera de Git)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def cargar_env(ruta=None):
    """Lector mínimo de .env: no pisa variables ya definidas en el entorno."""
    archivo = Path(ruta) if ruta else BASE_DIR / ".env"
    if not archivo.is_file():
        return
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _numero(nombre, defecto, tipo=float):
    try:
        valor = tipo(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return tipo(defecto)
    return valor if valor > 0 else tipo(defecto)


cargar_env()

DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "ecotech.db"))
LOG_PATH = os.environ.get("LOG_PATH", str(BASE_DIR / "ecotech.log"))
TIMEOUT = _numero("API_TIMEOUT", 5, float)
MAX_INTENTOS = min(_numero("API_MAX_INTENTOS", 3, int), 4)  # tope de la guía: 3 a 4

ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

GEOCODING_URL = os.environ.get("GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1/search")
PRONOSTICO_URL = os.environ.get("PRONOSTICO_URL", "https://api.open-meteo.com/v1/forecast")
CAMBIO_URL = os.environ.get("CAMBIO_URL", "https://open.er-api.com/v6/latest/USD")
MONEDA_BASE = "USD"
