# AWS — worker Lambda (ECR + S3 + SES)

CloudFormation para dejar el worker en AWS con **S3** (artefactos) y **SES** (correo).
Neon y Vercel quedan fuera. R2/Resend siguen soportados por parámetros si hace falta.

Plantilla: [`worker-lambda.yaml`](./worker-lambda.yaml)

## Qué crea

| Recurso | Uso |
|---------|-----|
| ECR | Imagen Docker (`Dockerfile.lambda`) |
| S3 | ZIP/PDF privados + lifecycle |
| Lambda | Procesa jobs (`app.lambda_handler.handler`) |
| Execution role | Logs, S3, SES |
| OIDC + rol Vercel | `lambda:InvokeFunction` + `s3:GetObject` (presign) |

No crea API Gateway, VPC ni NAT.

## Despliegue en 2 fases

La Lambda no puede crearse sin una imagen ya publicada en ECR.

### Fase 1 — ECR + S3 + IAM (`ImageUri` vacío)

```bash
aws cloudformation deploy \
  --region sa-east-1 \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker-qa \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-qa \
    FunctionName=tocheck-reportes-worker-qa \
    EcrRepositoryName=tocheck-reportes-worker-qa \
    VercelTeamSlug=Tocheck \
    VercelProjectName=generador-pdfs-masivos-web \
    VercelEnvironment=production \
    ExistingOidcProviderArn=arn:aws:iam::ACCOUNT:oidc-provider/oidc.vercel.com/Tocheck \
    StorageBackend=s3 \
    EmailBackend=ses \
    ImageUri=
```

Anota `EcrRepositoryUri` y `ArtifactsBucketName`.

### Fase 2 — build, push y crear Lambda

```bash
REGION=sa-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=tocheck-reportes-worker-qa
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:qa"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

docker build -f services/worker/Dockerfile.lambda -t "$IMAGE_URI" services/worker
docker push "$IMAGE_URI"

aws cloudformation deploy \
  --region sa-east-1 \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker-qa \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-qa \
    FunctionName=tocheck-reportes-worker-qa \
    EcrRepositoryName=tocheck-reportes-worker-qa \
    VercelTeamSlug=Tocheck \
    VercelProjectName=generador-pdfs-masivos-web \
    VercelEnvironment=production \
    ExistingOidcProviderArn=arn:aws:iam::ACCOUNT:oidc-provider/oidc.vercel.com/Tocheck \
    ImageUri="$IMAGE_URI" \
    DatabaseUrl="postgres://...neon...?sslmode=require" \
    SourceAdapter=snapshot \
    StorageBackend=s3 \
    EmailBackend=ses \
    SesRegion=sa-east-1 \
    EmailFrom=reportes@tocheck.cl
```

### Vercel

```env
WORKER_DISPATCH_PROVIDER=aws_lambda
AWS_REGION=sa-east-1
AWS_ROLE_ARN=...
AWS_LAMBDA_FUNCTION_NAME=tocheck-reportes-worker-qa
STORAGE_BACKEND=s3
AWS_S3_BUCKET=...
AWS_S3_REGION=sa-east-1
```

El mismo `AWS_ROLE_ARN` sirve para invocar Lambda y firmar descargas S3.

## Prueba rápida

```bash
aws lambda invoke \
  --region sa-east-1 \
  --function-name tocheck-reportes-worker-qa \
  --invocation-type Event \
  --cli-binary-format raw-in-base64-out \
  --payload '{"schemaVersion":1,"jobId":"<UUID-de-un-job-pending-en-Neon>"}' \
  /tmp/out.json
```

---

# Ingest diario (Lambda liviana + EventBridge)

Plantilla: [`ingest-lambda.yaml`](./ingest-lambda.yaml)  
Imagen: `services/worker/Dockerfile.ingest` (sin Playwright).

Agenda **04:00 America/Santiago** → lee MySQL (`RDS_*`) → escribe snapshot en Postgres (`DATABASE_URL`).

### Requisito de red

Si el RDS es privado / por SG, la Lambda **debe** ir en VPC (`VpcSubnetIds` + `VpcSecurityGroupIds` que el RDS permita).  
Esas subnets necesitan **NAT** (u otra salida) para alcanzar Neon si es público.

### Fase 1 — ECR

```bash
aws cloudformation deploy \
  --region sa-east-1 \
  --template-file infra/aws/ingest-lambda.yaml \
  --stack-name tocheck-reportes-ingest-qa \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-ingest-qa \
    FunctionName=tocheck-reportes-ingest-qa \
    EcrRepositoryName=tocheck-reportes-ingest-qa \
    ImageUri=
```

### Fase 2 — build, push, Lambda + schedule

```bash
REGION=sa-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/tocheck-reportes-ingest-qa:qa"

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
  --region sa-east-1 \
  --template-file infra/aws/ingest-lambda.yaml \
  --stack-name tocheck-reportes-ingest-qa \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=tocheck-reportes-ingest-qa \
    FunctionName=tocheck-reportes-ingest-qa \
    EcrRepositoryName=tocheck-reportes-ingest-qa \
    ImageUri="$IMAGE_URI" \
    DatabaseUrl="postgres://...neon...?sslmode=require" \
    RdsHost="....rds.amazonaws.com" \
    RdsUser=readonly_user \
    RdsPass="..." \
    RdsDb=tocheck_prod \
    CompanyIds=254 \
    ScheduleExpression="cron(0 4 * * ? *)" \
    ScheduleTimezone=America/Santiago
    # Si RDS es privado, descomenta y completa:
    # VpcSubnetIds=subnet-aaa,subnet-bbb \
    # VpcSecurityGroupIds=sg-xxx
```

### Prueba manual (sin esperar a las 4:00)

```bash
aws lambda invoke \
  --region sa-east-1 \
  --function-name tocheck-reportes-ingest-qa \
  --cli-binary-format raw-in-base64-out \
  --payload '{"schemaVersion":1,"companyIds":"254","lookbackDays":7}' \
  /tmp/ingest-out.json && cat /tmp/ingest-out.json
```
