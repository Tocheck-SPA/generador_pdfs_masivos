# AWS — worker Lambda (ECR + S3 + SES)

CloudFormation para dejar el worker en AWS con **S3** (artefactos) y **SES** (correo).
Neon y Vercel quedan fuera. R2/Resend siguen soportados por parámetros si hace falta.

**Región (worker + ingest): `us-east-1`** — mismo que RDS ToCheck y SES (`no-reply@tocheck.cl`).

Plantilla: [`worker-lambda.yaml`](./worker-lambda.yaml)

| Entorno | Script | Sufijo recursos | Tag imagen |
|---------|--------|-----------------|------------|
| QA | [`deploy-qa.sh`](./deploy-qa.sh) | `*-qa` | `:qa` |
| PROD | [`deploy-prod.sh`](./deploy-prod.sh) | `*-prod` | `:prod` |

Lógica compartida: [`deploy-common.inc.sh`](./deploy-common.inc.sh)

## Qué crea

| Recurso | Uso |
|---------|-----|
| ECR | Imagen Docker (`Dockerfile.lambda`) |
| S3 | ZIP/PDF privados + lifecycle |
| Lambda | Procesa jobs (`app.lambda_handler.handler`) |
| Execution role | Logs, S3, SES |
| OIDC + rol Vercel | `lambda:InvokeFunction` + `s3:GetObject` (presign) |

No crea API Gateway, VPC ni NAT.

### Antes de migrar desde sa-east-1

Los `RoleName` IAM son **globales**. Si los stacks viejos (`*-qa`) existen en São Paulo:

```bash
aws cloudformation delete-stack --region sa-east-1 --stack-name tocheck-reportes-worker-qa
aws cloudformation delete-stack --region sa-east-1 --stack-name tocheck-reportes-ingest-qa
aws cloudformation wait stack-delete-complete --region sa-east-1 --stack-name tocheck-reportes-worker-qa
aws cloudformation wait stack-delete-complete --region sa-east-1 --stack-name tocheck-reportes-ingest-qa
```

(El bucket S3 del worker suele quedar con `DeletionPolicy: Retain`; bórralo a mano si no lo necesitas.)

### OIDC Vercel ↔ AWS

Si al crear un trabajo falla con `web identity token could not be validated`:

1. En Vercel → Project → Settings → Security → **OIDC issuer mode** (Team vs Global).
2. Fallback: `WORKER_AWS_ACCESS_KEY_ID` / `WORKER_AWS_SECRET_ACCESS_KEY`.

## Despliegue worker en 2 fases (`us-east-1`)

### Opción A — script

```bash
# QA
# Edita DATABASE_URL (y RDS_*) en infra/aws/deploy-qa.sh
./infra/aws/deploy-qa.sh phase1
./infra/aws/deploy-qa.sh phase2
./infra/aws/deploy-qa.sh outputs
./infra/aws/deploy-qa.sh ingest1
./infra/aws/deploy-qa.sh ingest2

# PROD
# Edita DATABASE_URL (y RDS_*) en infra/aws/deploy-prod.sh
./infra/aws/deploy-prod.sh phase1
./infra/aws/deploy-prod.sh phase2
./infra/aws/deploy-prod.sh outputs
./infra/aws/deploy-prod.sh ingest1
./infra/aws/deploy-prod.sh ingest2
```

### Opción B — comandos manuales

#### Fase 1 — ECR + S3 + IAM (`ImageUri` vacío)

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

aws cloudformation deploy \
  --region us-east-1 \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-prod \
    FunctionName=tocheck-reportes-worker-prod \
    EcrRepositoryName=tocheck-reportes-worker-prod \
    VercelTeamSlug=tocheck \
    VercelProjectName=generador-pdfs-masivos-web \
    VercelEnvironment=production \
    ExistingOidcProviderArn=arn:aws:iam::${ACCOUNT}:oidc-provider/oidc.vercel.com/tocheck \
    StorageBackend=s3 \
    EmailBackend=ses \
    SesRegion=us-east-1 \
    EmailFrom=no-reply@tocheck.cl \
    MemorySizeMB=4096 \
    EphemeralStorageMB=5120 \
    ImageUri=
```

Anota `EcrRepositoryUri` y `ArtifactsBucketName`.

#### Fase 2 — build, push y crear Lambda

```bash
REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=tocheck-reportes-worker-prod
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:prod"

aws ecr get-login-password --region "$REGION" \
  | sudo docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

sudo docker build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f services/worker/Dockerfile.lambda \
  -t "$IMAGE_URI" \
  services/worker
sudo docker push "$IMAGE_URI"

aws cloudformation deploy \
  --region us-east-1 \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-prod \
    FunctionName=tocheck-reportes-worker-prod \
    EcrRepositoryName=tocheck-reportes-worker-prod \
    VercelTeamSlug=tocheck \
    VercelProjectName=generador-pdfs-masivos-web \
    VercelEnvironment=production \
    ExistingOidcProviderArn=arn:aws:iam::${ACCOUNT}:oidc-provider/oidc.vercel.com/tocheck \
    ImageUri="$IMAGE_URI" \
    DatabaseUrl="postgres://...neon...?sslmode=require" \
    SourceAdapter=snapshot \
    StorageBackend=s3 \
    EmailBackend=ses \
    SesRegion=us-east-1 \
    EmailFrom=no-reply@tocheck.cl \
    MemorySizeMB=4096 \
    EphemeralStorageMB=5120
```

### Vercel

```env
WORKER_DISPATCH_PROVIDER=aws_lambda
WORKER_AWS_REGION=us-east-1
WORKER_AWS_ROLE_ARN=arn:aws:iam::ACCOUNT:role/tocheck-reportes-prod-vercel-invoke
WORKER_LAMBDA_FUNCTION_NAME=tocheck-reportes-worker-prod
STORAGE_BACKEND=s3
AWS_S3_BUCKET=tocheck-reportes-prod-artifacts-ACCOUNT-us-east-1
AWS_S3_REGION=us-east-1
```

(Aliases `WORKER_*` porque Vercel reserva varios `AWS_*`.)

## Rebuild rápido (imagen ya existente)

```bash
REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/tocheck-reportes-worker-prod:prod"

aws ecr get-login-password --region "$REGION" \
  | sudo docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

sudo docker build \
  --platform linux/amd64 --provenance=false --sbom=false \
  -f services/worker/Dockerfile.lambda -t "$IMAGE_URI" services/worker
sudo docker push "$IMAGE_URI"

aws lambda update-function-code \
  --region "$REGION" \
  --function-name tocheck-reportes-worker-prod \
  --image-uri "$IMAGE_URI"
aws lambda wait function-updated --region "$REGION" --function-name tocheck-reportes-worker-prod
```

## Prueba rápida

```bash
aws lambda invoke \
  --region us-east-1 \
  --function-name tocheck-reportes-worker-prod \
  --invocation-type Event \
  --cli-binary-format raw-in-base64-out \
  --payload '{"schemaVersion":1,"jobId":"<UUID-de-un-job-pending-en-Neon>"}' \
  /tmp/out.json
```

```bash
aws lambda invoke \
  --region us-east-1 \
  --function-name tocheck-reportes-worker-prod \
  --cli-binary-format raw-in-base64-out \
  --payload '{"debug":"chromium"}' \
  /tmp/chromium-probe.json && cat /tmp/chromium-probe.json
```

---

# Ingest diario (Lambda liviana + EventBridge)

Plantilla: [`ingest-lambda.yaml`](./ingest-lambda.yaml)  
Imagen: `services/worker/Dockerfile.ingest` (sin Playwright).  
**Región: `us-east-1`** (mismo que RDS ToCheck y el worker).

Agenda **04:00 America/Santiago** → lee MySQL (`RDS_*`) → escribe snapshot en Postgres (`DATABASE_URL`).

### Requisito de red

Si el RDS es privado / por SG, la Lambda **debe** ir en VPC (`VpcSubnetIds` + `VpcSecurityGroupIds` que el RDS permita).  
Esas subnets necesitan **NAT** (u otra salida) para alcanzar Neon si es público.

### Fase 1 — ECR

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --template-file infra/aws/ingest-lambda.yaml \
  --stack-name tocheck-reportes-ingest-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-ingest-prod \
    FunctionName=tocheck-reportes-ingest-prod \
    EcrRepositoryName=tocheck-reportes-ingest-prod \
    ImageUri=
```

### Fase 2 — build, push, Lambda + schedule

```bash
REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/tocheck-reportes-ingest-prod:prod"

aws ecr get-login-password --region "$REGION" \
  | sudo docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

sudo docker build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f services/worker/Dockerfile.ingest \
  -t "$IMAGE_URI" \
  services/worker
sudo docker push "$IMAGE_URI"

aws cloudformation deploy \
  --region us-east-1 \
  --template-file infra/aws/ingest-lambda.yaml \
  --stack-name tocheck-reportes-ingest-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-ingest-prod \
    FunctionName=tocheck-reportes-ingest-prod \
    EcrRepositoryName=tocheck-reportes-ingest-prod \
    ImageUri="$IMAGE_URI" \
    DatabaseUrl="postgres://...neon...?sslmode=require" \
    RdsHost="....rds.amazonaws.com" \
    RdsUser=readonly_user \
    RdsPass="..." \
    RdsDb="..." \
    CompanyIds=... \
    ScheduleExpression="cron(0 4 * * ? *)" \
    ScheduleTimezone=America/Santiago
    # Si RDS es privado, descomenta y completa (subnets us-east-1):
    # VpcSubnetIds=subnet-aaa,subnet-bbb \
    # VpcSecurityGroupIds=sg-xxx
```

### Prueba manual (sin esperar a las 4:00)

```bash
aws lambda invoke \
  --region us-east-1 \
  --function-name tocheck-reportes-ingest-prod \
  --cli-binary-format raw-in-base64-out \
  --payload '{"schemaVersion":1,"companyIds":"254","lookbackDays":7}' \
  /tmp/ingest-out.json && cat /tmp/ingest-out.json
```
