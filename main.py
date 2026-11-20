"""EcoTech Solutions - Consumo seguro de APIs y resiliencia (ES3, TI3021)."""
import getpass
import logging
import sqlite3
import sys

import config
import seguridad
import servicios
import validadores as v
from api_cliente import ClienteApi
from db import BaseDatos
from errores import (ErrorApi, ErrorAutenticacion, ErrorValidacion)
from modelos import antiguedad

log = logging.getLogger("ecotech")
MAX_INTENTOS_LOGIN = 3


def configurar_logging():
    """El detalle técnico va al archivo; el usuario solo ve mensajes seguros."""
    logging.basicConfig(
        filename=config.LOG_PATH, level=logging.INFO, encoding="utf-8",
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def pedir(texto, validador, intentos=3):
    for _ in range(intentos):
        try:
            return validador(input(texto))
        except ErrorValidacion as e:
            print(f"  ✗ {e}")
    raise ErrorValidacion("Demasiados intentos inválidos.")


def sembrar_admin(db):
    """Crea el usuario inicial desde .env, una sola vez y con la clave hasheada."""
    if not (config.ADMIN_USER and config.ADMIN_PASSWORD):
        return
    try:
        if not db.existe_usuario(config.ADMIN_USER):
            seguridad.registrar_usuario(db, config.ADMIN_USER, config.ADMIN_PASSWORD)
    except ErrorValidacion as e:
        log.warning("No se pudo sembrar el usuario inicial: %s", e)


def iniciar_sesion(db, sesion):
    for restantes in range(MAX_INTENTOS_LOGIN, 0, -1):
        try:
            usuario = input("Usuario: ")
            password = getpass.getpass("Contraseña: ")
            sesion.iniciar(seguridad.autenticar(db, usuario, password))
            print(f"\n✓ Bienvenido/a, {sesion.usuario}.")
            return True
        except (ErrorValidacion, ErrorAutenticacion) as e:
            print(f"  ✗ {e} Intentos restantes: {restantes - 1}")
    print("Demasiados intentos fallidos. Saliendo.")
    return False


def registrar(db):
    try:
        usuario = pedir("Nuevo usuario: ", v.validar_usuario)
        p1 = getpass.getpass("Contraseña (mín. 8, letras y números): ")
        p2 = getpass.getpass("Repite la contraseña: ")
        if p1 != p2:
            raise ErrorValidacion("Las contraseñas no coinciden.")
        seguridad.registrar_usuario(db, usuario, p1)
        print("✓ Usuario creado. Ya puedes iniciar sesión.")
    except ErrorValidacion as e:
        print(f"  ✗ {e}")


def pantalla_acceso(db, sesion):
    while True:
        print("\n=== EcoTech Solutions ===\n1) Iniciar sesión\n2) Crear usuario\n0) Salir")
        op = input("Opción: ").strip()
        if op == "1":
            return iniciar_sesion(db, sesion)
        if op == "2":
            registrar(db)
        elif op == "0":
            return False
        else:
            print("  ✗ Opción no válida.")


def _linea_origen(res):
    if res.origen == "api":
        return "Fuente: API en línea (datos actualizados ahora)."
    return (f"⚠ Servicio no disponible: {res.aviso}\n"
            f"  Mostrando datos locales guardados {antiguedad(res.dato.obtenido_en)} "
            f"(obtenido_en: {res.dato.obtenido_en}).")


def opcion_clima(sesion, cliente, db):
    ciudad = pedir("Ciudad: ", v.validar_ciudad)
    pais = pedir("País (código de 2 letras, ej. CL): ", v.validar_pais)
    res = servicios.obtener_clima(sesion, ciudad, pais, cliente, db)
    c = res.dato
    print(f"\nClima en {c.ciudad} ({c.pais}): {c.temperatura_c:.1f} °C, "
          f"humedad {c.humedad_pct:.0f}%, {c.estado}.")
    print(_linea_origen(res))


def opcion_cambio(sesion, cliente, db):
    moneda = pedir("Moneda destino (ej. CLP, EUR, BRL): ", v.validar_moneda)
    res = servicios.obtener_tasa(sesion, moneda, cliente, db)
    t = res.dato
    print(f"\n1 {t.base} = {t.tasa} {t.moneda}")
    print(_linea_origen(res))


def opcion_pago(sesion, cliente, db):
    monto = pedir("Monto del pago en USD: ", v.validar_monto)
    moneda = pedir("Moneda del país del proyecto (ej. CLP): ", v.validar_moneda)
    res = servicios.obtener_tasa(sesion, moneda, cliente, db)
    t = res.dato
    pago = servicios.calcular_pago(monto, t.tasa)
    print(f"\nPago ajustado: {monto:,.2f} {t.base} -> {pago:,.2f} {t.moneda} (tasa {t.tasa})")
    print(_linea_origen(res))


def opcion_datos(db):
    print("\n-- Clima almacenado --")
    for f in db.listar_clima() or [{}]:
        print(f"  {f['ciudad']} ({f['pais']}): {f['temperatura_c']:.1f} °C, "
              f"{f['estado']} | obtenido_en {f['obtenido_en']}" if f else "  (sin datos)")
    print("-- Tipos de cambio almacenados --")
    for f in db.listar_tasas() or [{}]:
        print(f"  1 {f['base']} = {f['tasa']} {f['moneda']} | obtenido_en {f['obtenido_en']}"
              if f else "  (sin datos)")


def menu(sesion, cliente, db):
    acciones = {"1": opcion_clima, "2": opcion_cambio, "3": opcion_pago}
    while True:
        print("\n--- Menú ---\n1) Consultar clima\n2) Consultar tipo de cambio\n"
              "3) Calcular pago internacional\n4) Ver datos almacenados\n0) Cerrar sesión")
        op = input("Opción: ").strip()
        if op == "0":
            sesion.cerrar()
            print("Sesión cerrada.")
            return
        try:
            if op in acciones:
                acciones[op](sesion, cliente, db)
            elif op == "4":
                sesion.exigir()
                opcion_datos(db)
            else:
                print("  ✗ Opción no válida.")
        except ErrorValidacion as e:
            print(f"  ✗ {e}")
        except ErrorAutenticacion as e:
            print(f"  ✗ {e}")
            return
        except ErrorApi as e:
            print(f"  ✗ {e}")
        except sqlite3.Error:
            log.exception("Error de base de datos")
            print("  ✗ Error al acceder a la base de datos local.")
        except Exception:  # última barrera: se registra TODO el detalle y se informa sin exponerlo
            log.exception("Error inesperado en el menú")
            print("  ✗ Ocurrió un error inesperado. El detalle quedó en el registro.")


def main():
    configurar_logging()
    try:
        db = BaseDatos()
    except sqlite3.Error:
        log.exception("No se pudo abrir la base de datos")
        print("✗ No se pudo abrir la base de datos local.")
        return 1
    sembrar_admin(db)
    sesion = seguridad.Sesion()
    cliente = ClienteApi()
    try:
        if pantalla_acceso(db, sesion):
            menu(sesion, cliente, db)
    except (KeyboardInterrupt, EOFError):
        print("\nSaliendo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
