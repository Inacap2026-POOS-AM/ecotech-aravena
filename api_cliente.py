"""Cliente HTTP seguro y resiliente (requests).

- timeout explícito en TODA petición (nunca se espera indefinidamente)
- 4xx  -> NO se reintenta (la solicitud está mal; reintentar no la arregla)
- 429  -> se respeta el encabezado Retry-After
- 5xx / red / timeout -> se reintenta, con backoff exponencial y tope de intentos
- verificación TLS activa (no se usa verify=False)
"""
import logging
import random
import time

import requests

import config
from errores import ErrorApi, ErrorDatos, ErrorDisponibilidad, ErrorSolicitud

log = logging.getLogger("ecotech.api")

MAX_ESPERA = 30.0  # tope de cualquier espera (segundos)
_HEADERS = {"User-Agent": "EcoTech-ES3/1.0", "Accept": "application/json"}


class ClienteApi:
    def __init__(self, timeout=None, max_intentos=None, backoff_base=1.0,
                 sesion=None, dormir=time.sleep):
        self.timeout = config.TIMEOUT if timeout is None else timeout
        self.max_intentos = config.MAX_INTENTOS if max_intentos is None else max_intentos
        self.backoff_base = backoff_base
        self._sesion = sesion or requests.Session()
        self._dormir = dormir

    def _backoff(self, intento):
        """1s, 2s, 4s... (+ jitter pequeño para no sincronizar reintentos)."""
        espera = self.backoff_base * (2 ** (intento - 1))
        espera += random.uniform(0, 0.25 * self.backoff_base)
        return min(espera, MAX_ESPERA)

    @staticmethod
    def _retry_after(resp):
        """Segundos indicados por el servidor, o None si falta/no es numérico."""
        try:
            return min(max(float(resp.headers.get("Retry-After")), 0.0), MAX_ESPERA)
        except (TypeError, ValueError):
            return None

    def get_json(self, url, params=None):
        """GET con política de reintentos. Devuelve el JSON ya parseado."""
        motivo = "sin detalle"
        for intento in range(1, self.max_intentos + 1):
            try:
                resp = self._sesion.get(url, params=params, headers=_HEADERS,
                                        timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                motivo = type(exc).__name__
                espera = self._backoff(intento)
            except requests.RequestException as exc:
                log.error("Solicitud inválida (%s)", type(exc).__name__)
                raise ErrorSolicitud("No se pudo construir la solicitud al servicio.") from exc
            else:
                codigo = resp.status_code
                if 200 <= codigo < 300:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ErrorDatos("El servicio respondió con un formato no válido.") from exc
                if codigo == 429:
                    motivo = "HTTP 429"
                    espera = self._retry_after(resp) or self._backoff(intento)
                elif 500 <= codigo < 600:
                    motivo = f"HTTP {codigo}"
                    espera = self._backoff(intento)
                elif 400 <= codigo < 500:
                    log.error("Respuesta %s del servicio (no se reintenta)", codigo)
                    raise ErrorSolicitud(
                        f"El servicio rechazó la solicitud (HTTP {codigo}); no se reintenta.")
                else:
                    raise ErrorApi(f"Respuesta inesperada del servicio (HTTP {codigo}).")

            log.warning("Intento %d/%d falló: %s", intento, self.max_intentos, motivo)
            if intento < self.max_intentos:
                self._dormir(espera)

        raise ErrorDisponibilidad(
            f"El servicio externo no está disponible ({motivo}) tras {self.max_intentos} intentos.")
