"""Pruebas sin internet: simulan las 4 pruebas en vivo de C14 con respuestas falsas."""
import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal

import requests

import seguridad
import servicios
from api_cliente import ClienteApi
from db import BaseDatos
from errores import (ErrorAutenticacion, ErrorDisponibilidad, ErrorSinDatos,
                     ErrorSolicitud, ErrorValidacion)
import validadores as v

GEO = {"results": [{"country_code": "CL", "latitude": -33.45, "longitude": -70.66}]}
PRON = {"current": {"temperature_2m": 21.5, "relative_humidity_2m": 40, "weather_code": 0}}
CAMBIO = {"result": "success", "base_code": "USD", "rates": {"CLP": 950.25, "EUR": 0.92}}


class Resp:
    def __init__(self, codigo=200, datos=None, headers=None):
        self.status_code, self._d, self.headers = codigo, datos, headers or {}

    def json(self):
        if self._d is None:
            raise ValueError("no json")
        return self._d


class SesionFalsa:
    """Entrega respuestas/errores en orden y cuenta las llamadas."""
    def __init__(self, *guion):
        self.guion, self.llamadas = list(guion), 0

    def get(self, url, **kw):
        assert kw.get("timeout"), "toda petición debe llevar timeout"
        self.llamadas += 1
        item = self.guion.pop(0) if len(self.guion) > 1 else self.guion[0]
        if isinstance(item, Exception):
            raise item
        return item


def cliente(*guion, esperas=None):
    s = SesionFalsa(*guion)
    c = ClienteApi(timeout=5, max_intentos=3, backoff_base=1.0, sesion=s,
                   dormir=(esperas.append if esperas is not None else lambda _: None))
    return c, s


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = BaseDatos(os.path.join(self.tmp, "t.db"))
        self.ses = seguridad.Sesion()
        self.ses.iniciar("tester")


class TestCliente(Base):
    def test_404_no_se_reintenta(self):
        c, s = cliente(Resp(404))
        with self.assertRaises(ErrorSolicitud):
            c.get_json("http://x")
        self.assertEqual(s.llamadas, 1)

    def test_429_respeta_retry_after(self):
        esperas = []
        c, s = cliente(Resp(429, headers={"Retry-After": "7"}), Resp(200, {"ok": 1}), esperas=esperas)
        self.assertEqual(c.get_json("http://x"), {"ok": 1})
        self.assertEqual(esperas, [7.0])

    def test_5xx_reintenta_con_backoff_y_se_acota(self):
        esperas = []
        c, s = cliente(Resp(503), esperas=esperas)
        with self.assertRaises(ErrorDisponibilidad):
            c.get_json("http://x")
        self.assertEqual(s.llamadas, 3)               # máximo 3 intentos
        self.assertEqual(len(esperas), 2)             # no duerme tras el último
        self.assertGreaterEqual(esperas[1], esperas[0] * 1.5)  # crece (exponencial)

    def test_red_caida_se_reintenta(self):
        c, s = cliente(requests.ConnectionError("sin red"))
        with self.assertRaises(ErrorDisponibilidad):
            c.get_json("http://x")
        self.assertEqual(s.llamadas, 3)

    def test_recupera_tras_fallo_transitorio(self):
        c, s = cliente(requests.Timeout(), Resp(200, {"ok": 1}))
        self.assertEqual(c.get_json("http://x"), {"ok": 1})


class TestServicios(Base):
    def test_ejecucion_consecutiva_es_idempotente(self):
        for _ in range(2):
            c, _ = cliente(Resp(200, GEO), Resp(200, PRON))
            servicios.obtener_clima(self.ses, "santiago", "cl", c, self.db)
            c2, _ = cliente(Resp(200, CAMBIO))
            servicios.obtener_tasa(self.ses, "clp", c2, self.db)
        self.assertEqual(len(self.db.listar_clima()), 1)
        self.assertEqual(len(self.db.listar_tasas()), 1)

    def test_corte_de_red_usa_plan_b_con_antiguedad(self):
        c, _ = cliente(Resp(200, GEO), Resp(200, PRON))
        servicios.obtener_clima(self.ses, "Santiago", "CL", c, self.db)
        caido, _ = cliente(requests.ConnectionError("sin wifi"))
        r = servicios.obtener_clima(self.ses, "Santiago", "CL", caido, self.db)
        self.assertEqual(r.origen, "local")
        self.assertTrue(r.dato.obtenido_en)
        self.assertEqual(r.dato.temperatura_c, 21.5)

    def test_sin_red_y_sin_datos_da_error_controlado(self):
        caido, _ = cliente(requests.ConnectionError("x"))
        with self.assertRaises(ErrorSinDatos):
            servicios.obtener_clima(self.ses, "Lima", "PE", caido, self.db)

    def test_url_invalida_404_cae_a_plan_b(self):
        c, _ = cliente(Resp(200, CAMBIO))
        servicios.obtener_tasa(self.ses, "CLP", c, self.db)
        malo, s = cliente(Resp(404))
        r = servicios.obtener_tasa(self.ses, "CLP", malo, self.db)
        self.assertEqual(r.origen, "local")
        self.assertIn("404", r.aviso)
        self.assertEqual(s.llamadas, 1)

    def test_json_corrupto_se_rechaza(self):
        c, _ = cliente(Resp(200, {"result": "success", "base_code": "USD", "rates": {"CLP": "abc"}}))
        with self.assertRaises(ErrorSinDatos):
            servicios.obtener_tasa(self.ses, "CLP", c, self.db)

    def test_sin_sesion_no_se_consume_la_api(self):
        c, s = cliente(Resp(200, CAMBIO))
        with self.assertRaises(ErrorAutenticacion):
            servicios.obtener_tasa(seguridad.Sesion(), "CLP", c, self.db)
        self.assertEqual(s.llamadas, 0)

    def test_sesion_expirada(self):
        t = [0.0]
        ses = seguridad.Sesion(ttl_segundos=10, reloj=lambda: t[0])
        ses.iniciar("x")
        t[0] = 11
        with self.assertRaises(ErrorAutenticacion):
            ses.exigir()

    def test_calculo_de_pago(self):
        self.assertEqual(servicios.calcular_pago(Decimal("1500"), Decimal("950.25")), Decimal("1425375.00"))


class TestSeguridad(Base):
    def test_contrasena_nunca_en_texto_plano(self):
        seguridad.registrar_usuario(self.db, "ana", "Clave12345")
        with sqlite3.connect(self.db.ruta) as con:
            h = con.execute("SELECT password_hash FROM usuarios").fetchone()[0]
        self.assertNotIn("Clave12345", h)
        self.assertTrue(h.startswith("$2"))  # formato bcrypt

    def test_login_correcto_e_incorrecto(self):
        seguridad.registrar_usuario(self.db, "ana", "Clave12345")
        self.assertEqual(seguridad.autenticar(self.db, "ana", "Clave12345"), "ana")
        with self.assertRaises(ErrorAutenticacion):
            seguridad.autenticar(self.db, "ana", "otra-clave-9")
        with self.assertRaises(ErrorAutenticacion):
            seguridad.autenticar(self.db, "fantasma", "Clave12345")

    def test_usuario_duplicado(self):
        seguridad.registrar_usuario(self.db, "ana", "Clave12345")
        with self.assertRaises(ErrorValidacion):
            seguridad.registrar_usuario(self.db, "ana", "Clave12345")

    def test_inyeccion_sql_queda_como_dato(self):
        malo = "x'); DROP TABLE usuarios;--"
        with self.assertRaises(ErrorValidacion):
            v.validar_usuario(malo)                 # la validación la frena primero
        self.assertIsNone(self.db.obtener_hash(malo))   # y aunque llegara, es parámetro
        self.assertEqual(self.db.listar_clima(), [])    # tablas intactas

    def test_validadores(self):
        for malo in ["", "  ", "Santiago123", "Sant'; DROP", "<script>", "a" * 61]:
            with self.assertRaises(ErrorValidacion):
                v.validar_ciudad(malo)
        self.assertEqual(v.validar_ciudad("  san   josé "), "San José")
        for malo in ["CHL", "C", "1A", ""]:
            with self.assertRaises(ErrorValidacion):
                v.validar_pais(malo)
        for malo in ["-5", "0", "abc", "1e999", "nan", "2000000"]:
            with self.assertRaises(ErrorValidacion):
                v.validar_monto(malo)
        self.assertEqual(v.validar_monto("1.500,5".replace(".", "")), Decimal("1500.5"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
