# Bitácora de uso de IA – ES3 TI3021

- **Herramienta:** Claude (Anthropic), chat web
- **Fecha:** 20-nov-2026
- **Uso:** apoyo para generar la primera versión del cliente, la capa de datos y la seguridad; luego revisé, probé y ajusté el código.
- **Evidencia de verificación:** `test_offline.py` (18 pruebas, sin internet) y las búsquedas `grep` de la sección 3.

> Nota personal: antes de entregar, lee cada entrada y comprueba que coincide con lo que realmente
> hiciste. Esta bitácora vale solo si la puedes defender oralmente.

## 1. Registro de prompts

| N.º | Prompt (resumen) | Qué entregó la IA | Qué hice yo |
|---|---|---|---|
| 1 | Cliente HTTP en Python con `requests` para consumir clima y tipo de cambio, con timeout, reintentos y manejo de errores | `ClienteApi` con reintentos y backoff | Revisé cada rama: 4xx sin reintento, 429 con `Retry-After`, 5xx/red con backoff y máximo 3 intentos. Lo probé con respuestas simuladas |
| 2 | Persistencia SQLite sin duplicados al correr el script dos veces | Tablas con `UNIQUE` y `INSERT ... ON CONFLICT DO UPDATE` | Verifiqué idempotencia ejecutando dos veces y contando filas |
| 3 | Login con contraseñas cifradas y validación de entradas | bcrypt, validadores por lista blanca, sesión con expiración | Probé login correcto/incorrecto, usuario inexistente, duplicado y entradas maliciosas |
| 4 | Plan B cuando la API no responde | Lectura de datos locales con `obtenido_en` | Simulé corte de red y 404; comprobé que muestra la antigüedad del dato |

## 2. Auditoría de las 5 señales de riesgo

### Señal 1 – f-strings / concatenación en SQL
- **Código inseguro típico que suele proponer una IA:** `cursor.execute(f"INSERT INTO clima VALUES ('{ciudad}', {temp})")`
- **Riesgo:** inyección SQL. Con `ciudad = "x'); DROP TABLE clima;--"` se ejecutaría código del atacante.
- **Decisión:** **descartado**.
- **Solución aplicada:** todas las consultas de `db.py` usan placeholders `?` con una tupla de valores. El DDL (`CREATE TABLE`) es estático y no recibe datos del usuario. Además, `validadores.py` rechaza caracteres no permitidos antes de llegar a la base.
- **Evidencia:** `test_inyeccion_sql_queda_como_dato` y `grep -n "execute(f" *.py` sin resultados.

### Señal 2 – `verify=False`
- **Código inseguro típico:** `requests.get(url, verify=False)` "para evitar errores de certificado".
- **Riesgo:** desactiva la verificación TLS; permite ataques man-in-the-middle y datos falsificados.
- **Decisión:** **descartado**.
- **Solución aplicada:** `ClienteApi` no pasa `verify`, así que `requests` verifica el certificado por defecto.
- **Evidencia:** `grep -n "verify" *.py` solo aparece en un comentario.

### Señal 3 – `except: pass`
- **Código inseguro típico:** `try: ... except: pass`.
- **Riesgo:** oculta errores y deja el sistema en estado inconsistente; dificulta depurar y puede mostrar datos vacíos como si fueran válidos.
- **Decisión:** **modificado**.
- **Solución aplicada:** jerarquía de excepciones propias (`errores.py`): `ErrorSolicitud`, `ErrorDisponibilidad`, `ErrorDatos`, `ErrorSinDatos`, `ErrorValidacion`, `ErrorAutenticacion`. Cada una se captura por separado en `servicios.py` y `main.py`. El detalle técnico va a `ecotech.log` y el usuario ve un mensaje seguro. Existe un único `except Exception` al final del menú, que registra el traceback con `log.exception` y no lo oculta.
- **Evidencia:** `grep -nE "except\s*:" *.py` sin resultados.

### Señal 4 – Llamadas sin `timeout`
- **Código inseguro típico:** `requests.get(url)`.
- **Riesgo:** sin `timeout` la petición puede quedar esperando indefinidamente y congelar el sistema.
- **Decisión:** **modificado**.
- **Solución aplicada:** hay un único punto de salida HTTP (`ClienteApi.get_json`) y siempre pasa `timeout=` (5 s por defecto, configurable en `.env`). Las pruebas fallan si una petición no lo incluye.
- **Evidencia:** `SesionFalsa.get` en `test_offline.py` hace `assert kw.get("timeout")`.

### Señal 5 – Librerías inexistentes en PyPI (slopsquatting)
- **Riesgo:** una IA puede inventar nombres de paquetes; si un atacante registra ese nombre, `pip install` instala código malicioso.
- **Decisión:** solo uso dependencias que verifiqué en pypi.org: `requests` (Python Software Foundation) y `bcrypt` (Python Cryptographic Authority). El resto es librería estándar (`sqlite3`, `decimal`, `logging`, `dataclasses`, `re`).
- **Solución aplicada:** `requirements.txt` solo lista esas dos, con versión mínima.

## 3. Otras vulnerabilidades detectadas y corregidas

| Hallazgo | Cómo se corrigió |
|---|---|
| Contraseñas en texto plano o con hash rápido sin salt (MD5/SHA-256) | bcrypt con salt por contraseña (`seguridad.py`); verificado en `test_contrasena_nunca_en_texto_plano` |
| Llaves y credenciales dentro del código | Variables de entorno en `.env` (en `.gitignore`); solo se sube `.env.example` |
| Mensajes de error con traza, URL o datos internos | Mensajes seguros al usuario; detalle solo en `ecotech.log` |
| Reintentos infinitos o sin espera | Máximo 3 intentos, backoff exponencial, 4xx sin reintento, `Retry-After` en 429 |
| Confiar en el JSON de la API | `deserializadores.py` valida estructura, tipos, rangos y coherencia |
| Acceso a APIs sin autenticación | La capa de servicios exige `Sesion` válida (con expiración): sin login no hay consumo |
| Revelar si un usuario existe | Mensaje único "Credenciales inválidas" y verificación contra un hash señuelo |

## 4. Decisiones de uso de la IA

- **Aceptado con revisión:** estructura general (cliente, deserializador, servicios, base de datos).
- **Modificado:** manejo de excepciones, política de reintentos, validadores y mensajes al usuario.
- **Descartado:** cualquier patrón de las 5 señales de la sección 2.
- **Limitación conocida:** `Retry-After` solo se interpreta como número de segundos; si el servidor envía una fecha HTTP, se usa el backoff exponencial.
