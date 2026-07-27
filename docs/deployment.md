# Despliegue — ToCheck Reportes

Guía paso a paso para pasar del MVP con fixtures a producción.

## 0. Requisitos

- Cuentas en: Neon, Vercel, Cloud Run, Cloudflare R2, Resend, GitHub.
- Acceso de **solo lectura** a la base de datos de ToCheck.

## 1. Crear la base operativa en Neon

1. Crea un proyecto en Neon y una base `tocheck_reportes`.
2. Copia la connection string (con `?sslmode=require`).

## 2. Ejecutar migraciones

```bash
DATABASE_URL="postgres://...neon.../tocheck_reportes?sslmode=require" \
  node scripts/migrate.mjs
```

Aplica `database/migrations/0001_init.sql`. Es idempotente (registra en `schema_migrations`).

## 3. Configurar Auth.js (Google OAuth)

1. En Google Cloud Console crea credenciales OAuth 2.0.
2. Authorized redirect URI: `https://TU-DOMINIO/api/auth/callback/google`.
3. Define `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEXTAUTH_SECRET` (genera uno con `openssl rand -base64 32`).
4. Restringe acceso con `AUTH_ALLOWED_DOMAINS=tocheck.cl` y/o `AUTH_ALLOWED_EMAILS=...`.
5. En producción pon `AUTH_DEV_MODE=false` (desactiva el login por correo sin contraseña).

## 4. Ingesta local de la fuente

1. En la base de ToCheck, crea un rol de solo lectura:
   ```sql
   CREATE ROLE tocheck_ro LOGIN PASSWORD '...';
   GRANT CONNECT ON DATABASE <db> TO tocheck_ro;
   GRANT USAGE ON SCHEMA public TO tocheck_ro;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO tocheck_ro;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO tocheck_ro;
   ```
2. La máquina autorizada conserva `RDS_*` y ejecuta `python -m app.main ingest --company-id 254 --lookback-days 7`.
   Web y worker usarán `SOURCE_ADAPTER=snapshot` para leer el contenido de Neon.

## 5–6. Configurar R2 y credenciales

1. Crea un bucket **privado** en Cloudflare R2.
2. Genera un API token S3 (Access Key ID + Secret).
3. Variables: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
   `R2_ENDPOINT` (`https://<account>.r2.cloudflarestorage.com`), `R2_REGION=auto`,
   `STORAGE_BACKEND=r2`.
4. **Lifecycle rules** recomendadas en el bucket:
   - Expirar objetos bajo `reports/` a los `REPORT_RETENTION_DAYS` (90) días.
   - Las URLs de descarga se firman con `REPORT_LINK_EXPIRATION_DAYS` (15) días.

## 7–8. Configurar Resend y verificar dominio

1. Crea una API key en Resend → `RESEND_API_KEY`, `EMAIL_BACKEND=resend`.
2. Verifica el dominio remitente (`EMAIL_FROM=reportes@tocheck.cl`) con los registros DNS que indica Resend.
3. Opcional: `EMAIL_REPLY_TO`.

## 9. Desplegar la web en Vercel

1. Importa el repo; **Root Directory = `apps/web`**.
2. Carga las variables de entorno (sección Web + `DATABASE_URL`).
3. Deploy. Verifica `https://TU-DOMINIO/api/health`.

## 10. Desplegar el worker como Cloud Run Job

1. Construye la imagen desde `services/worker` y súbela a Artifact Registry.
2. Crea el Job con `DATABASE_URL` (Neon), `SOURCE_ADAPTER=snapshot`, `R2_*`, `RESEND_*`,
   límites y configuración PDF.
3. Comando: `python -m app.main run-once`.
4. El botón de la web ejecuta el Job después de crear el registro en Neon.

## 11. Variables de entorno

Ver `.env.example` (lista completa y comentada).

## 12–17. Validación progresiva

12. Prueba con fixtures: `python -m app.main demo` dentro del contenedor.
13. Ejecuta la ingesta y prueba con una empresa real y un rango **pequeño** (`SOURCE_ADAPTER=snapshot`).
14. Ejecuta un rango pequeño desde la UI.
15. Valida el PDF generado (contenido, fotos, acentos, saltos de página).
16. Valida el correo (adjunto vs enlace, expiración).
17. Aumenta gradualmente `MAX_RESPONSES_PER_JOB` y el rango de fechas.

## Notas operativas

## Snapshot incremental MySQL → Neon

La fuente AWS RDS tiene una restricción de IP, por lo que producción no la consulta
directamente. La máquina local que tiene la IP autorizada ejecuta periódicamente:

```bash
python -m app.main ingest --company-id 254
```

**La ingesta es incremental por fecha y hora, no por día.** Sin `--date-from`, la
corrida continúa exactamente desde el instante (`date_to_exclusive` con hora, minuto,
segundo y microsegundo) donde terminó la última corrida `completed` para esa empresa
(`resolve_ingest_window` en `app/source/ingest.py`). Así, si se ejecuta varias veces al
día, nunca pierde respuestas nuevas dentro del mismo día ni reprocesa el rango ya cubierto.
Solo si nunca hubo una corrida exitosa cae a `--lookback-days` (por defecto 7, desde
medianoche) como respaldo inicial. El fin, si no se especifica, es el instante actual
(no "mañana a medianoche"), para que la siguiente corrida continúe sin huecos.

Para un backfill manual (primera carga o recuperar un rango específico), pasa
`--date-from`/`--date-to-exclusive` explícitos — esto siempre tiene prioridad sobre la
continuación automática:

```bash
python -m app.main ingest --company-id 254 --date-from 2026-07-01T00:00:00
```

La ingesta reutiliza las consultas MySQL existentes, guarda el payload necesario por
respuesta en `source_response_snapshots` y registra cada corrida, incluyendo `company_id`,
en `source_sync_runs`. La escritura es idempotente (`ON CONFLICT DO UPDATE` por
`response_id`), por lo que solapar rangos entre corridas es seguro, solo desperdicia
trabajo, nunca corrompe datos.
Web y worker usan `SOURCE_ADAPTER=snapshot` y leen desde Neon. Las imágenes no se copian;
se conservan sus rutas públicas para resolverlas al generar el PDF.

## Cloud Run Job bajo demanda

El contenedor se ejecuta con `python -m app.main run-once`: reclama como máximo un job,
lo procesa y termina. El botón de la web debe ejecutar el Cloud Run Job después de crear
el registro en Neon. Como el worker ya no accede a AWS, esta arquitectura no requiere
VPC, Cloud NAT ni IP estática en Google Cloud.

- **Recuperación de trabajos abandonados:** un job cuyo `heartbeat_at` supera
  `WORKER_STALE_AFTER_SECONDS` se re-reclama, sin exceder `WORKER_MAX_ATTEMPTS` y sin
  reenviar correo (la consulta de claim excluye jobs con correo `sent`).
- **Idempotencia de correo:** clave `idempotency_key:email` en `email_deliveries`.

## Portabilidad de ejecución y almacenamiento

La UI no depende de una implementación concreta del worker. Selecciona el
despachador mediante `WORKER_DISPATCH_PROVIDER`:

- `disabled`: crea el job, pero no intenta despertarlo.
- `gcp_cloud_run`: ejecuta un Cloud Run Job con `run-job --job-id UUID`.
- `aws_lambda`: invoca la función Lambda con `{ schemaVersion: 1, jobId }`.

El destino de los artefactos se selecciona por separado con `STORAGE_BACKEND`:
`local`, `r2` o `s3`. En producción debe usarse `r2` o `s3`; la API web genera
URLs firmadas para descargar los PDF/ZIP y no expone las claves internas.

El cambio entre Lambda y Cloud Run requiere cambiar variables de entorno y
configurar el permiso del proveedor elegido. El código queda preparado, pero
la validación final exige credenciales, permisos IAM/WIF, imagen publicada y
un job real en cada nube.
