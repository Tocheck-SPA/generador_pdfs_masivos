# Handoff: worker portable entre Cloud Run y Lambda

## Objetivo

La UI permanece en Vercel, lee y crea jobs en Neon, y despierta un worker que
puede ejecutarse en Google Cloud Run Jobs o AWS Lambda. El almacenamiento de
PDFs/ZIP es independiente del proveedor de cómputo y puede ser Cloudflare R2 o
AWS S3.

## Selectores de producción

```env
WORKER_DISPATCH_PROVIDER=gcp_cloud_run|aws_lambda|disabled
STORAGE_BACKEND=r2|s3|local
```

Ejemplos válidos:

```env
# Cloud Run + R2
WORKER_DISPATCH_PROVIDER=gcp_cloud_run
STORAGE_BACKEND=r2

# Lambda + S3
WORKER_DISPATCH_PROVIDER=aws_lambda
STORAGE_BACKEND=s3
```

La ingesta continúa ejecutándose desde una máquina autorizada contra MySQL/RDS
y escribe en Neon. Web y worker usan `SOURCE_ADAPTER=snapshot`.

## Contrato del job

La API crea primero el job en Neon y luego llama:

```ts
dispatchWorkerJob({ jobId, request })
```

El worker recibe o ejecuta:

```text
python -m app.main run-job --job-id UUID
```

Lambda recibe el evento equivalente:

```json
{
  "schemaVersion": 1,
  "jobId": "UUID"
}
```

El claim es atómico y dirigido por ID. Una ejecución repetida del mismo job no
debe generar un segundo PDF ni reenviar el correo.

## Google Cloud

Vercel usa OIDC y Workload Identity Federation. El dispatcher ejecuta el Cloud
Run Job con `containerOverrides` para pasar `run-job --job-id UUID`.

Variables principales:

```env
GCP_PROJECT_ID=
CLOUD_RUN_REGION=
CLOUD_RUN_JOB_NAME=
GCP_WORKLOAD_IDENTITY_PROJECT_NUMBER=
GCP_WORKLOAD_IDENTITY_POOL=
GCP_WORKLOAD_IDENTITY_PROVIDER=
GCP_SERVICE_ACCOUNT_EMAIL=
```

El service account necesita permiso para ejecutar el Job con overrides. No usar
claves JSON de service account.

## AWS Lambda

La imagen está en `services/worker/Dockerfile.lambda` y usa el mismo núcleo
Python/Playwright que Cloud Run, pero con `awslambdaric` y
`app.lambda_handler.handler`.

Infra como código (ECR + Lambda + OIDC Vercel, sin API Gateway/VPC):
ver [infra/aws/README.md](../infra/aws/README.md) y
[infra/aws/worker-lambda.yaml](../infra/aws/worker-lambda.yaml).

Variables principales en Vercel:

```env
AWS_REGION=
AWS_ROLE_ARN=
AWS_LAMBDA_FUNCTION_NAME=
AWS_LAMBDA_QUALIFIER=
```

Vercel debe asumir un IAM Role mediante OIDC con permiso mínimo
`lambda:InvokeFunction` sobre esa Lambda. No usar access keys permanentes.

## R2 y S3

Los artefactos se registran en Neon con:

```text
storage_provider
storage_bucket
storage_key
```

La UI firma la descarga bajo demanda según el proveedor guardado en el
artefacto. Por eso los reportes históricos siguen descargables aunque cambie
`STORAGE_BACKEND`.

### R2

```env
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_ENDPOINT=
R2_REGION=auto
```

### S3 (recomendado en AWS)

```env
STORAGE_BACKEND=s3
AWS_S3_BUCKET=
AWS_S3_REGION=sa-east-1
AWS_S3_PREFIX=reports
```

El CloudFormation en `infra/aws/` crea el bucket y otorga permisos al rol de
Lambda (put/get) y al rol OIDC de Vercel (get/presign). No uses access keys
permanentes. Cloud Run, si se usa, debe recibir credenciales temporales o
secretos administrados.

## Acciones de TI

### Google Cloud

- Artifact Registry.
- Cloud Run Job.
- Workload Identity Pool/Provider para Vercel.
- Service account con permiso de ejecución del Job.
- Cloud Logging.

No se requiere VPC, Cloud NAT ni IP estática mientras el worker solo use Neon,
R2/S3 público/privado mediante credenciales y Resend.

### AWS

- ECR.
- Lambda basada en container image.
- Execution Role con CloudWatch Logs y S3 si `STORAGE_BACKEND=s3`.
- OIDC Provider de Vercel.
- IAM Role de Vercel limitado a invocar la función.

No se requiere VPC ni acceso a RDS para el worker productivo.

## Validación local

```bash
npm run typecheck --workspace apps/web
npm run test --workspace apps/web
npm run build --workspace apps/web

cd services/worker
ruff check app tests
python -m py_compile app/main.py app/lambda_handler.py
pytest
```

## Validación cloud pendiente

No se considera validado hasta disponer de:

- Permisos OIDC de Vercel en GCP.
- Permisos OIDC de Vercel en AWS.
- Imagen publicada en Artifact Registry/ECR.
- Buckets R2/S3 configurados.
- Variables de entorno productivas.
- Un job real de empresa 254 con BPM Foodtruck 1.1 e imágenes.

La validación real debe comprobar PDF, foto, logos, ZIP, URL firmada, correo,
estado Neon y descarga desde la UI.
