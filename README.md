# broker-salud API

Este repositorio contiene el backend principal de CELDOCTOR. Expone la API que usa el frontend web, concentra la logica de negocio y persiste datos en PostgreSQL.

## Rol del backend dentro de la plataforma

La API resuelve casi todo lo sensible del producto:

- autenticacion y autorizacion
- usuarios y perfiles
- suscripciones y estado del plan
- beneficiarios del plan familiar
- empresas y empleados
- facturacion
- soporte y tickets
- leads comerciales
- credenciales digitales y validacion QR
- upsells
- canal comercial

La web en Next.js consume esta API a traves de un proxy interno. El navegador no deberia hablar directo con FastAPI en el flujo normal del producto.

## Stack

| Capa | Tecnologia |
| --- | --- |
| API | FastAPI |
| ASGI server | Uvicorn |
| ORM / acceso DB | SQLAlchemy 2 |
| Migraciones | Alembic |
| Base de datos | PostgreSQL |
| Rate limiting | SlowAPI |
| Redis | soporte listo para rate limiting compartido |
| Auth | JWT con `python-jose` |
| Password hashing | Passlib + bcrypt |
| Email | Resend |
| Excel | openpyxl |
| QR | qrcode |

## Entry points principales

- `app/main.py`
  Crea la aplicacion FastAPI, configura CORS, docs, healthcheck y registra routers.
- `app/database.py`
  Inicializa engine y sesion SQLAlchemy.
- `app/auth.py`
  JWT, hashing y dependencias de usuario actual.
- `app/settings.py`
  Configuracion centralizada por ambiente.
- `app/serve.py`
  Arranque con variables de runtime.

## Routers disponibles

En `app/routers/` hoy estan estos modulos:

- `auth.py`
- `usuarios.py`
- `planes.py`
- `suscripciones.py`
- `beneficiarios.py`
- `catalogo.py`
- `soporte.py`
- `leads.py`
- `facturacion.py`
- `empresas.py`
- `credenciales.py`
- `upsells.py`
- `comercial.py`
- `admin.py`
- `admin_common.py`

Eso te da una idea bastante fiel de los dominios que ya cubre el producto.

## Organizacion de la logica

La logica de negocio esta separada en `app/services/` por vertical:

- `admin/`
- `catalogo/`
- `comercial/`
- `credenciales/`
- `email/`
- `empresas/`
- `facturacion/`
- `soporte/`
- `suscripciones/`
- `upsells/`

Este esquema permite crecer por dominio sin dejar todo dentro de los routers.

## Modelo mental del sistema

### Clientes

El backend permite:

- registrarse
- iniciar sesion
- consultar perfil
- consultar suscripcion
- ver credencial
- administrar beneficiarios
- abrir tickets

### Admin

El panel administrativo consume endpoints para:

- metricas y overview
- personas
- empresas
- suscripciones
- tickets
- leads
- upsells
- catalogo
- canal comercial

### Canal comercial

El backend maneja:

- brokers
- vendedores directos
- vendedores de broker
- links de referido
- panel comercial por rol

### Credenciales

El modulo de credenciales resuelve:

- token QR
- expiracion corta del QR
- validacion publica del token
- payload de beneficio asociado

## Variables de entorno

La configuracion actual vive en `app/settings.py` y se documenta tambien en `.env.example`.

Variables principales:

```env
APP_ENV=development
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/broker_salud
SECRET_KEY=changeme_super_secret_key
QR_SECRET=changeme_qr_secret
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
REDIS_URL=redis://localhost:6379/0
JOB_QUEUE_NAME=celdoctor:jobs
JOB_RETRY_LIMIT=3
ENABLE_DOCS=true
ENABLE_REDOC=true
QR_DEFAULT_BENEFIT_TYPE=farmacia
FARMACIA_DESCUENTO_PORCENTAJE=40
SERVICE_TOKEN=changeme_internal_service_token
RESEND_API_KEY=...
ADMIN_EMAIL=admin@celdoctor.com
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
WEB_CONCURRENCY=2
UVICORN_KEEP_ALIVE=30
```

### Notas importantes

- `DATABASE_URL` y `SECRET_KEY` son obligatorias.
- `QR_SECRET` cae a `SECRET_KEY` si no existe.
- en produccion, `/docs` y `/redoc` pueden quedar deshabilitados por ambiente.
- `REDIS_URL` ya esta prevista para el siguiente paso de rate limiting y jobs compartidos.
- `SERVICE_TOKEN` protege los endpoints internos de cron.
- `JOB_QUEUE_NAME` y `JOB_RETRY_LIMIT` gobiernan la cola Redis simple usada por emails y jobs operativos.

## Migraciones

Este repo ya tiene infraestructura Alembic:

- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/`

Comandos utiles:

```bash
python -m alembic heads
python -m alembic upgrade head
python -m alembic revision -m "descripcion_del_cambio"
```

Direccion tecnica actual:

- los cambios de schema deben pasar por Alembic
- los guards runtime existentes se estan dejando como compatibilidad temporal y se iran retirando

## Desarrollo local

### 1. Instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar entorno

```bash
copy .env.example .env
```

### 3. Aplicar migraciones

```bash
python -m alembic upgrade head
```

### 4. Levantar API

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Levantar worker de jobs

Si `REDIS_URL` esta configurada, conviene correr un worker aparte para vaciar la cola:

```bash
python -m app.serve_worker
```

Sin Redis, el sistema hace fallback a `BackgroundTasks` o a ejecucion directa, segun el flujo.

Healthcheck:

- [http://localhost:8000/health](http://localhost:8000/health)

## Flujo de autenticacion

El backend expone `POST /auth/login` y devuelve:

- `access_token`
- `token_type`
- `usuario`

El frontend no deberia persistir ese token en JS sensible; la capa web lo recibe y lo guarda como cookie `httpOnly` desde Next.

## Rate limiting

El proyecto usa SlowAPI. Ya esta listo para evolucionar de memoria local a Redis compartido:

- sin `REDIS_URL`: usa memoria del proceso
- con `REDIS_URL`: puede pasar a un storage compartido real

## Emails

El modulo `app/services/email/` centraliza layouts y notificaciones:

- recuperacion de contrasena
- avisos operativos
- mensajes internos del producto

Hoy los emails ya pueden salir por Redis si `REDIS_URL` esta configurada. Si no, hacen fallback limpio a `BackgroundTasks` o a ejecucion directa.

## Jobs internos y cron

El backend expone un canal interno protegido para tareas operativas:

- `POST /internal/jobs/procesar-vencimientos`
- `POST /internal/jobs/enviar-recordatorios`

Estos endpoints aceptan:

- `X-Service-Token: <SERVICE_TOKEN>`
- o `Authorization: Bearer <SERVICE_TOKEN>`

Si hay Redis disponible:

- el endpoint encola el job y responde rapido
- el worker `python -m app.jobs.worker` lo procesa despues

Si Redis no esta disponible:

- el endpoint ejecuta el job inline como fallback

Ejemplo de llamada:

```bash
curl -X POST https://api.celdoctor.com/internal/jobs/procesar-vencimientos ^
  -H "X-Service-Token: tu_service_token"
```

En Railway, la idea es que Cron pegue a esos endpoints y el worker se encargue del trabajo pesado.

## Backups y recuperacion

Esto es critico para produccion. La recomendacion para CELDOCTOR es trabajar con **dos capas de backup**:

### 1. Backups nativos de Railway

Para el servicio Postgres en Railway:

- activar schedule **daily**
- activar schedule **weekly**
- activar schedule **monthly**
- crear un backup manual antes de cada migracion Alembic importante
- bloquear snapshots clave para que no se borren por error

Runbook minimo sugerido:

1. antes de migrar: crear backup manual
2. correr `alembic upgrade head`
3. si algo sale mal: restaurar snapshot en Railway y revisar el deploy antes de aplicar

### 2. Backups logicos propios

Este repo incluye scripts en:

- `tools/backups/backup_postgres.py`
- `tools/backups/restore_postgres.py`
- `tools/backups/README.md`

Ejemplo de dump logico:

```bash
python tools/backups/backup_postgres.py --label pre_migracion
```

Eso genera:

- archivo `.dump`
- checksum `.sha256`
- metadata `.json`

Ejemplo de restore:

```bash
python tools/backups/restore_postgres.py backups/celdoctor_pre_migracion_20260419_120000.dump --yes
```

### Politica recomendada

- Railway snapshots para recuperacion rapida
- dump logico previo a migraciones y cambios grandes
- restore probado al menos una vez en staging
- nunca depender de una sola capa de backup

## Credenciales QR

El backend genera y valida credenciales digitales. Variables relevantes:

- `QR_SECRET`
- `QR_TOKEN_SECONDS`
- `QR_DEFAULT_BENEFIT_TYPE`
- `FARMACIA_DESCUENTO_PORCENTAJE`

Eso alimenta la experiencia de la credencial del cliente y la pagina publica de validacion.

## Testing de capacidad

El repo ya incluye un kit de pruebas en:

- `tools/capacity/README.md`

Incluye:

- benchmark HTTP
- probe de base de datos
- siembra local masiva para probar 100k usuarios sin tocar produccion

## Despliegue esperado

### Railway

Este servicio esta pensado para correr en Railway con:

- PostgreSQL
- Redis
- variables por ambiente
- workers Uvicorn configurables

### Vercel

El frontend en Vercel consume esta API a traves de:

- `BACKEND_URL`

En produccion idealmente:

```env
BACKEND_URL=https://api.celdoctor.com
FRONTEND_URL=https://www.celdoctor.com
```

## Como entender el backend rapido

Si alguien nuevo entra al repo, este orden ayuda mucho:

1. `app/main.py`
2. `app/settings.py`
3. `app/auth.py`
4. `app/database.py`
5. `app/routers/auth.py`
6. `app/routers/suscripciones.py`
7. `app/routers/empresas.py`
8. `app/routers/comercial.py`
9. `app/services/`
10. `alembic/versions/`

Con ese recorrido se entiende la base del sistema sin tener que leer todo de golpe.

## Estado actual y foco cercano

El backend ya soporta una buena parte del negocio, pero de cara al lanzamiento los bloques tecnicos mas cercanos son:

- consolidar staging
- activar Redis por ambiente
- cerrar cron real y jobs async
- robustecer pagos y webhooks
- terminar de limpiar guards de schema heredados

La base esta lo suficientemente ordenada como para avanzar en eso sin rearmar el proyecto desde cero.
