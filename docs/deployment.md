# Despliegue — ToCheck Reportes

Guía paso a paso para pasar del MVP con fixtures a producción.

## 0. Requisitos

- Cuentas en: Neon, Vercel, Railway, Cloudflare R2, Resend, GitHub.
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

## 4. Conexión de solo lectura a la fuente

1. En la base de ToCheck, crea un rol de solo lectura:
   ```sql
   CREATE ROLE tocheck_ro LOGIN PASSWORD '...';
   GRANT CONNECT ON DATABASE <db> TO tocheck_ro;
   GRANT USAGE ON SCHEMA public TO tocheck_ro;
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO tocheck_ro;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO tocheck_ro;
   ```
2. Define `SOURCE_DATABASE_URL` (SSL), `SOURCE_DATABASE_SSLMODE=require`, `SOURCE_ADAPTER=postgres`.

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

## 10. Desplegar el worker en Railway

1. Nuevo servicio desde el repo, **Root = `services/worker`** (usa el `Dockerfile`).
2. Variables: `DATABASE_URL` (Neon), `SOURCE_*`, `R2_*`, `RESEND_*`, `WORKER_*`, límites y PDF.
3. Comando: `python -m app.main run` (por defecto en el Dockerfile).
4. Escala a 1 réplica al inicio; el claim con `SKIP LOCKED` permite escalar horizontalmente después.

## 11. Variables de entorno

Ver `.env.example` (lista completa y comentada).

## 12–17. Validación progresiva

12. Prueba con fixtures: `python -m app.main demo` dentro del contenedor.
13. Prueba con una empresa real y un rango **pequeño** (`SOURCE_ADAPTER=postgres`).
14. Ejecuta un rango pequeño desde la UI.
15. Valida el PDF generado (contenido, fotos, acentos, saltos de página).
16. Valida el correo (adjunto vs enlace, expiración).
17. Aumenta gradualmente `MAX_RESPONSES_PER_JOB` y el rango de fechas.

## Notas operativas

- **Recuperación de trabajos abandonados:** un job cuyo `heartbeat_at` supera
  `WORKER_STALE_AFTER_SECONDS` se re-reclama, sin exceder `WORKER_MAX_ATTEMPTS` y sin
  reenviar correo (la consulta de claim excluye jobs con correo `sent`).
- **Idempotencia de correo:** clave `idempotency_key:email` en `email_deliveries`.
