# ToCheck Reportes

Aplicación interna, paralela a ToCheck, para **seleccionar respuestas de checklist,
generar un PDF por respuesta, agruparlas en un ZIP y enviarlas por correo** a uno o
varios destinatarios. No modifica el sistema principal de ToCheck: la base fuente se
consulta **solo lectura**.

> Estado: **MVP funcional**. Corre de punta a punta en local con *fixtures*, sin
> credenciales ni servicios externos. Ver [Criterios de aceptación](#criterios-de-aceptación).

---

## Arquitectura

```
┌───────────────────────────┐        ┌───────────────────────────┐
│  Next.js (Vercel)          │        │  Worker Python (Railway)   │
│  UI · Auth · API rápida    │        │  Fuente → PDF → ZIP → R2   │
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
- **No se copian respuestas a Neon.** Solo metadatos operativos (jobs, ítems, artifacts,
  eventos, entregas de correo).

## Estructura del repositorio

```
apps/web/            Frontend Next.js (App Router, TS estricto, Auth.js, Zod)
services/worker/     Worker Python (psycopg3, Pydantic, Jinja2, Playwright, pypdf, Pillow, boto3)
  app/source/        SourceRepository (fixture + postgres) + consultas .sql divididas
  app/reports/       Modelo ReportData, builder, hashing, imágenes, render, ZIP
  app/storage/       Local + Cloudflare R2
  app/email/         Consola + Resend
  templates/         Plantilla Jinja2 del informe (fiel al Design System)
  tests/             Pytest (35 pruebas + integración de PDF real)
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

## Pruebas

```bash
# Worker
cd services/worker && .venv/Scripts/python -m pytest         # 35 pruebas
cd services/worker && .venv/Scripts/python -m ruff check app tests

# Web
cd apps/web && npm run typecheck && npm run lint && npm run test && npm run build
```

Las pruebas del *claim* atómico contra Postgres se activan con `TEST_DATABASE_URL`
(ver `services/worker/tests/test_db_claim.py`).

## Seguridad y minimización de datos

- Usuario de solo lectura en la fuente, conexión SSL, `statement_timeout`, consultas
  parametrizadas, límites de fecha/respuestas/destinatarios.
- **No se muestra ni persiste RUT**, ni correos personales innecesarios, ni coordenadas
  por defecto. Los logs son JSON y filtran claves sensibles y URLs firmadas.
- Bucket R2 privado con URLs prefirmadas temporales.

## Documentación

- [docs/deployment.md](docs/deployment.md) — despliegue paso a paso (Neon, Vercel, Railway, R2, Resend).
- [docs/decisions.md](docs/decisions.md) — decisiones técnicas y consultas SQL implementadas.
- [docs/pending-fields.md](docs/pending-fields.md) — campos de la fuente por confirmar y puntos de extensión.

## Criterios de aceptación

Verificado en local (ver informe de entrega): login, selección dependiente
empresa→formulario→puntos, conteo, creación inmediata de job, procesamiento por el
worker sin duplicar preguntas por fotos/firmas, PDF por respuesta con fotografías
(tolerando fallidas), preguntas adicionales, metadata de firmas y tickets, ZIP con
manifest, subida al almacenamiento, correo (adjunto o enlace según tamaño), progreso,
historial, descarga, idempotencia de correo y respeto del Design System.
