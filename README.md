# EcoTech Solutions – Consumo seguro de APIs y resiliencia (ES3 · TI3021)

Extensión del sistema de EcoTech: consulta **clima** (Open-Meteo, sin llave) y **tipo de cambio**
(open.er-api.com, sin llave), con login, validación, reintentos, Plan B local y persistencia SQLite.

## Ejecutar
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python main.py
python test_offline.py                                 # pruebas sin internet
```

## Archivos
| Archivo | Rol |
|---|---|
| `api_cliente.py` | Cliente `requests`: timeout, 4xx sin reintento, 429 + Retry-After, 5xx/red con backoff (máx. 3) |
| `deserializadores.py` | Valida y convierte el JSON externo a modelos propios |
| `servicios.py` | Casos de uso + **Plan B** (datos locales con `obtenido_en`); exige sesión |
| `db.py` | SQLite, consultas **parametrizadas**, upserts idempotentes |
| `seguridad.py` | bcrypt (con salt), autenticación, sesión con expiración |
| `validadores.py` | Lista blanca para ciudad, país, moneda, monto, usuario y contraseña |
| `bitacora_ia.md` | Auditoría de código generado por IA (5 señales de riesgo) |
| `.env.example` | Plantilla de configuración (el `.env` real NO se sube) |
