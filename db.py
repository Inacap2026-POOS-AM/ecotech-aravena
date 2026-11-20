"""Persistencia SQLite. TODAS las consultas usan parámetros (?): cero concatenación."""
import sqlite3
from contextlib import closing
from decimal import Decimal

import config
from modelos import Clima, TipoCambio

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    creado_en     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS clima (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ciudad_clave  TEXT NOT NULL,
    ciudad        TEXT NOT NULL,
    pais          TEXT NOT NULL,
    latitud       REAL NOT NULL,
    longitud      REAL NOT NULL,
    temperatura_c REAL NOT NULL,
    humedad_pct   REAL NOT NULL,
    estado        TEXT NOT NULL,
    obtenido_en   TEXT NOT NULL,
    UNIQUE (ciudad_clave, pais)
);
CREATE TABLE IF NOT EXISTS tipo_cambio (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    base        TEXT NOT NULL,
    moneda      TEXT NOT NULL,
    tasa        TEXT NOT NULL,
    obtenido_en TEXT NOT NULL,
    UNIQUE (base, moneda)
);
"""


class BaseDatos:
    def __init__(self, ruta=None):
        self.ruta = ruta or config.DB_PATH
        with closing(self._conectar()) as conn, conn:
            conn.executescript(ESQUEMA)  # DDL estático, sin datos del usuario

    def _conectar(self):
        conn = sqlite3.connect(self.ruta)
        conn.row_factory = sqlite3.Row
        return conn

    # ---------- usuarios ----------
    def crear_usuario(self, username, password_hash):
        """True si se creó; False si ya existía (idempotente, no duplica)."""
        with closing(self._conectar()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO usuarios (username, password_hash) VALUES (?, ?) "
                "ON CONFLICT(username) DO NOTHING",
                (username, password_hash),
            )
            return cur.rowcount == 1

    def obtener_hash(self, username):
        with closing(self._conectar()) as conn:
            fila = conn.execute(
                "SELECT password_hash FROM usuarios WHERE username = ?", (username,)
            ).fetchone()
        return fila["password_hash"] if fila else None

    def existe_usuario(self, username):
        return self.obtener_hash(username) is not None

    # ---------- clima ----------
    def guardar_clima(self, c):
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO clima (ciudad_clave, ciudad, pais, latitud, longitud, "
                "temperatura_c, humedad_pct, estado, obtenido_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(ciudad_clave, pais) DO UPDATE SET "
                "ciudad=excluded.ciudad, latitud=excluded.latitud, longitud=excluded.longitud, "
                "temperatura_c=excluded.temperatura_c, humedad_pct=excluded.humedad_pct, "
                "estado=excluded.estado, obtenido_en=excluded.obtenido_en",
                (c.ciudad.casefold(), c.ciudad, c.pais, c.latitud, c.longitud,
                 c.temperatura_c, c.humedad_pct, c.estado, c.obtenido_en),
            )

    def obtener_clima(self, ciudad, pais):
        with closing(self._conectar()) as conn:
            f = conn.execute(
                "SELECT * FROM clima WHERE ciudad_clave = ? AND pais = ?",
                (ciudad.casefold(), pais),
            ).fetchone()
        if not f:
            return None
        return Clima(f["ciudad"], f["pais"], f["latitud"], f["longitud"],
                     f["temperatura_c"], f["humedad_pct"], f["estado"], f["obtenido_en"])

    def listar_clima(self):
        with closing(self._conectar()) as conn:
            filas = conn.execute(
                "SELECT ciudad, pais, temperatura_c, humedad_pct, estado, obtenido_en "
                "FROM clima ORDER BY obtenido_en DESC"
            ).fetchall()
        return [dict(f) for f in filas]

    # ---------- tipo de cambio ----------
    def guardar_tasa(self, t):
        with closing(self._conectar()) as conn, conn:
            conn.execute(
                "INSERT INTO tipo_cambio (base, moneda, tasa, obtenido_en) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(base, moneda) DO UPDATE SET "
                "tasa=excluded.tasa, obtenido_en=excluded.obtenido_en",
                (t.base, t.moneda, str(t.tasa), t.obtenido_en),
            )

    def obtener_tasa(self, base, moneda):
        with closing(self._conectar()) as conn:
            f = conn.execute(
                "SELECT * FROM tipo_cambio WHERE base = ? AND moneda = ?", (base, moneda)
            ).fetchone()
        if not f:
            return None
        return TipoCambio(f["base"], f["moneda"], Decimal(f["tasa"]), f["obtenido_en"])

    def listar_tasas(self):
        with closing(self._conectar()) as conn:
            filas = conn.execute(
                "SELECT base, moneda, tasa, obtenido_en FROM tipo_cambio ORDER BY moneda"
            ).fetchall()
        return [dict(f) for f in filas]
