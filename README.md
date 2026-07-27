# ToCheck Reportes

Aplicación interna, paralela a ToCheck, para **seleccionar respuestas de checklist,
generar un PDF por respuesta, agruparlas en un ZIP y enviarlas por correo** a uno o
varios destinatarios. No modifica el sistema principal de ToCheck: la base fuente se
consulta **solo lectura**.

> Estado: **listo para handoff**. El flujo de datos, snapshots, PDF/ZIP y configuración
> portable están implementados. La validación cloud final depende de las cuentas de TI.

---

## Estado actual

El flujo de snapshots en Neon, la ingesta acotada por empresa y la generacion
de PDF/ZIP estan implementados y validados localmente. Neon ya tiene aplicadas
las migraciones `0001` a `0004`. El proyecto esta listo para handoff; queda
pendiente solamente el despliegue y la validacion final de la infraestructura
cloud (Vercel + Lambda o Cloud Run).

## Despliegue portable

La UI puede despertar el worker mediante `WORKER_DISPATCH_PROVIDER=disabled`,
`gcp_cloud_run` o `aws_lambda`. Los artefactos pueden persistirse en `r2` o
`s3` mediante `STORAGE_BACKEND`, sin cambiar el flujo de generación. El detalle
de configuración y handoff está en [docs/worker-portability-handoff.md](docs/worker-portability-handoff.md).

## Arquitectura

```
┌───────────────────────────┐        ┌───────────────────────────┐
│  Next.js (Vercel)          │        │  Worker Python              │
│  UI · Auth · API rápida    │        │  Lambda / Cloud Run         │
│  conteo · creación de jobs │        │  → correo (Resend)         │
└─────────────┬──────────────┘        └───────┬───────────┬───────┘
              │                                │           │
              ▼                                ▼           ▼
     ┌──────────────────┐            ┌───────────────┐ ┌──────────┐
     │ Neon PostgreSQL  │◀───────────│  ToCheck DB    │ │ R2 /     │
     │ jobs · items ·   │  cola       │  (solo lectura)│ │ Resend   │
      │ artifacts · ...  │  persistente└───────────────┘ └──────────┘
     └──────────────────┘
```

- **La web nunca consulta la base fuente directamente.** Las credenciales de la fuente
  solo viven en el worker (variables de entorno).
- **Neon es la cola persistente** (no Redis/Celery/Kafka). El worker reclama trabajos con
  `SELECT ... FOR UPDATE SKIP LOCKED`.
- **El progreso se consulta por polling** (2,5 s) desde la UI.
- **Neon conserva el snapshot diario de respuestas necesario para los informes**, además
  de los metadatos operativos. Las imágenes no se copian: se resuelven desde sus URLs públicas.

## Flujo de datos productivo

```text
MySQL/RDS de ToCheck
        |  ingesta desde una maquina con IP autorizada
        v
Neon: snapshots + cola de jobs + artefactos
        ^                         |
        |                         v
UI Next.js en Vercel  --->  Worker Lambda/Cloud Run
                                      |
                                      v
                            R2 o S3 + correo
```

- La ingesta consulta MySQL en modo solo lectura y se ejecuta por empresa.
- `SOURCE_COMPANY_ID` evita cargar toda la fuente; el comando exige empresa
  explicita y permite rangos de fecha.
- Web y worker productivos usan `SOURCE_ADAPTER=snapshot` y consultan Neon.
- Las imagenes publicas se resuelven con las rutas publicas de ToCheck,
  incluyendo logo de empresa y logo oficial de ToCheck.
- La UI muestra la fecha de ultima actualizacion del snapshot y advierte si el
  rango solicitado no esta cubierto.

## Estructura del repositorio

```
apps/web/            Frontend Next.js (App Router, TS estricto, Auth.js, Zod)
services/worker/     Worker Python (psycopg3, Pydantic, Jinja2, Playwright, pypdf, Pillow, boto3)
  app/source/        SourceRepository (fixture + postgres) + consultas .sql divididas
  app/reports/       Modelo ReportData, builder, hashing, imágenes, render, ZIP
  app/storage/       Local + Cloudflare R2 + AWS S3
  app/email/         Consola + Resend
  templates/         Plantilla Jinja2 del informe (fiel al Design System)
  tests/             Pytest (suite unitaria + integración de PDF real)
database/migrations/ Esquema versionado de Neon
fixtures/            Datos de prueba COMPARTIDOS por web y worker
docs/                Despliegue, decisiones, campos pendientes de la fuente
```

## Desarrollo local

### 1. Web (con fixtures, sin base de datos)

```bash
cd apps/web
npm install
cp ../../.env.example .env.local   # o crea uno mínimo (ver abajo)
npm run dev                        # http://localhost:3000
```

`.env.local` mínimo para desarrollo:

```
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=dev-secret-local-only
AUTH_DEV_MODE=true
SOURCE_ADAPTER=fixture
```

Sin `DATABASE_URL`, la web usa un **store en memoria con simulador de progreso**, de modo
que todo el flujo (login → conteo → crear job → progreso → historial) funciona sin worker.
En modo desarrollo, el login acepta cualquier correo (proveedor "Modo desarrollo").

### 2. Worker (genera PDF/ZIP reales desde fixtures)

```bash
cd services/worker
python -m venv .venv
.venv/Scripts/activate            # Windows;  source .venv/bin/activate en Linux/mac
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m app.main demo           # genera PDFs + ZIP en services/worker/output/
```

### 3. Todo junto con Postgres real (opcional)

```bash
docker compose up               # Postgres + worker
DATABASE_URL=postgres://tocheck:tocheck@localhost:5432/tocheck_reportes \
  node scripts/migrate.mjs --seed
# La web con DATABASE_URL usa Postgres (pgStore) en vez del simulador.
```

### 4. Conectar la fuente real (AWS RDS MySQL)

La base de ToCheck es **MySQL en AWS RDS**. La ingesta local trae datos con `SOURCE_ADAPTER=mysql`
y la convención `RDS_*`; web y worker productivos leen el snapshot con `SOURCE_ADAPTER=snapshot`.
En `services/worker/.env` local:

```
SOURCE_ADAPTER=mysql
RDS_HOST=...rds.amazonaws.com
RDS_PORT=3306
RDS_USER=readonly_user
RDS_PASS=...
RDS_DB=tocheck_prod
SOURCE_DATABASE_USE_SSL=false
SOURCE_ASSET_BASE_URL=https://tocheck.s3.amazonaws.com
SOURCE_LOGO_BASE_URL=https://app.tocheck.cl/public/upload/files/logo_empresa
TOCHECK_LOGO_URL=https://app.tocheck.cl/public/img_tocheck/logo_negro.png
STORAGE_BACKEND=local
EMAIL_BACKEND=console
```

Descubre IDs y genera informes reales sin Neon/R2/Resend:

```bash
python -m app.main health                       # verifica la conexión
python -m app.main catalog                       # empresas
python -m app.main catalog --company-id 254      # formularios
python -m app.main catalog --company-id 254 --form-id 100 \
    --date-from 2026-07-01T00:00:00 --date-to-exclusive 2026-08-01T00:00:00  # puntos + conteo
python -m app.main demo --company-id 254 --form-id 100 \
    --date-from 2026-07-01T00:00:00 --date-to-exclusive 2026-08-01T00:00:00  # PDFs+ZIP a output/
```

El adaptador reutiliza las 12 consultas `.sql` traduciendo el dialecto (`= ANY(...)` → `IN ...`).
La ingesta reutiliza esas consultas, guarda el snapshot en Neon y el worker productivo ya no
necesita conexión directa a AWS.

## Produccion: snapshot diario en Neon

La maquina que tiene la IP autorizada en AWS ejecuta la ingesta contra MySQL.
El worker productivo no consulta RDS: usa `SOURCE_ADAPTER=snapshot` y lee los
datos ya guardados en Neon.

Para actualizar una empresa:

```bash
cd services/worker
python -m app.main ingest --company-id 254 --lookback-days 7
```

La corrida incremental continua desde la ultima sincronizacion completada. Para
un backfill controlado se pueden indicar `--date-from` y `--date-to-exclusive`.

La UI consulta el estado del snapshot y muestra la ultima actualizacion y si el
rango solicitado esta cubierto.

## Worker bajo demanda

La UI crea primero el job en Neon y luego lo despacha segun:

```env
WORKER_DISPATCH_PROVIDER=disabled|gcp_cloud_run|aws_lambda
```

El contrato neutral es:

```text
python -m app.main run-job --job-id UUID
```

Lambda recibe `{ "schemaVersion": 1, "jobId": "UUID" }`. El claim dirigido
por `jobId` mantiene la seguridad ante reintentos y evita duplicar el correo.

## Artefactos y descargas

Los PDF, ZIP y manifest se registran en Neon con proveedor, bucket y clave de
almacenamiento. El backend web genera URLs firmadas bajo demanda:

```env
STORAGE_BACKEND=local|r2|s3
```

Ejemplos:

```env
# Lambda + S3
WORKER_DISPATCH_PROVIDER=aws_lambda
STORAGE_BACKEND=s3
AWS_S3_BUCKET=tocheck-reportes
AWS_S3_REGION=us-east-1

# Cloud Run + R2
WORKER_DISPATCH_PROVIDER=gcp_cloud_run
STORAGE_BACKEND=r2
R2_BUCKET=tocheck-reportes
```

Los artefactos existentes mantienen su proveedor historico, por lo que cambiar
el backend no rompe las descargas anteriores.

## Handoff de infraestructura

### UI en Vercel

- Root Directory: `apps/web`.
- `DATABASE_URL` apunta a Neon.
- `SOURCE_ADAPTER=snapshot`.
- `WORKER_DISPATCH_PROVIDER=aws_lambda` cuando Lambda esté disponible.
- Vercel usa OIDC para invocar Lambda; no se requieren access keys permanentes.

### Worker en AWS

TI puede usar el CloudFormation en `infra/aws/` (ECR + Lambda + rol OIDC) o
publicar `services/worker/Dockerfile.lambda` en ECR y crear una Lambda
basada en esa imagen. La función recibe `{ "schemaVersion": 1, "jobId": "UUID" }`
y usa las mismas variables de Neon, almacenamiento y correo del worker.

No se requiere acceso del worker a MySQL/RDS. La única validación pendiente de
infraestructura es publicar la imagen, configurar IAM/OIDC y ejecutar un smoke
test real desde la UI.

## Pruebas

```bash
# Worker
cd services/worker && .venv/Scripts/python -m pytest
cd services/worker && .venv/Scripts/python -m ruff check app tests

# Web
cd apps/web && npm run typecheck && npm run lint && npm run test && npm run build
```

Las pruebas del *claim* atómico contra Postgres se activan con `TEST_DATABASE_URL`
(ver `services/worker/tests/test_db_claim.py`).

La suite también cubre el contrato Lambda, el claim dirigido por `jobId`, la
resolución de imágenes/logos, el almacenamiento S3 y la ingesta incremental.

## Seguridad y minimización de datos

- Usuario de solo lectura en la fuente, conexión SSL, `statement_timeout`, consultas
  parametrizadas, límites de fecha/respuestas/destinatarios.
- **No se muestra ni persiste RUT**, ni correos personales innecesarios, ni coordenadas
  por defecto. Los logs son JSON y filtran claves sensibles y URLs firmadas.
- Buckets R2/S3 privados con URLs prefirmadas temporales.

## Documentación

- [docs/deployment.md](docs/deployment.md) — despliegue paso a paso (Neon, Vercel, Lambda/Cloud Run, R2/S3, Resend).
- [docs/worker-portability-handoff.md](docs/worker-portability-handoff.md) — handoff para TI: Lambda, Cloud Run, OIDC, R2 y S3.
- [docs/decisions.md](docs/decisions.md) — decisiones técnicas y consultas SQL implementadas.
- [docs/pending-fields.md](docs/pending-fields.md) — campos de la fuente por confirmar y puntos de extensión.

## Criterios de aceptación

Verificado localmente: login, selección dependiente
empresa→formulario→puntos, conteo, creación inmediata de job, procesamiento por el
worker sin duplicar preguntas por fotos/firmas, PDF por respuesta con fotografías
(tolerando fallidas), preguntas adicionales, metadata de firmas y tickets, ZIP con
manifest, subida al almacenamiento, correo (adjunto o enlace según tamaño), progreso,
historial, descarga, idempotencia de correo y respeto del Design System.

La validación cloud final debe comprobar una corrida real desde la UI, el
procesamiento Lambda o Cloud Run, la descarga del ZIP mediante URL firmada y el
envío de correo con las variables productivas.
