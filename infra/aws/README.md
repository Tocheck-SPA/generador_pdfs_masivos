# AWS — worker Lambda (ECR)

CloudFormation para dejar **solo el worker** en AWS. R2, Resend, Neon y Vercel quedan fuera.

Plantilla: [`worker-lambda.yaml`](./worker-lambda.yaml)

## Qué crea

| Recurso | Uso |
|---------|-----|
| ECR | Imagen Docker (`Dockerfile.lambda`) |
| Lambda | Procesa jobs (`app.lambda_handler.handler`) |
| Execution role | Logs de CloudWatch |
| OIDC + rol Vercel | `lambda:InvokeFunction` vía OIDC (sin access keys) |

No crea API Gateway, VPC ni NAT.

## Despliegue en 2 fases

La Lambda no puede crearse sin una imagen ya publicada en ECR.

### Fase 1 — ECR + IAM (`ImageUri` vacío)

```bash
aws cloudformation deploy \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    VercelTeamSlug=TU_TEAM \
    VercelProjectName=TU_PROYECTO \
    VercelEnvironment=production \
    ImageUri=
```

Anota el output `EcrRepositoryUri`.

### Fase 2 — build, push y crear Lambda

```bash
REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=tocheck-reportes-worker
IMAGE_URI="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest"

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"

docker build -f services/worker/Dockerfile.lambda -t "$IMAGE_URI" services/worker
docker push "$IMAGE_URI"

aws cloudformation deploy \
  --template-file infra/aws/worker-lambda.yaml \
  --stack-name tocheck-reportes-worker \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    VercelTeamSlug=TU_TEAM \
    VercelProjectName=TU_PROYECTO \
    ImageUri="$IMAGE_URI" \
    DatabaseUrl="postgres://...neon...?sslmode=require" \
    SourceAdapter=snapshot \
    StorageBackend=r2 \
    R2AccountId=... \
    R2AccessKeyId=... \
    R2SecretAccessKey=... \
    R2Bucket=... \
    R2Endpoint="https://....r2.cloudflarestorage.com" \
    EmailBackend=resend \
    ResendApiKey=re_... \
    EmailFrom=reportes@tocheck.cl
```

Si el OIDC de Vercel ya existe en la cuenta, pasa `ExistingOidcProviderArn=arn:aws:iam::...:oidc-provider/oidc.vercel.com/TU_TEAM`.

### Vercel

Con los outputs del stack:

```env
WORKER_DISPATCH_PROVIDER=aws_lambda
AWS_REGION=...
AWS_ROLE_ARN=...          # VercelInvokeRoleArn
AWS_LAMBDA_FUNCTION_NAME=tocheck-reportes-worker
SOURCE_ADAPTER=snapshot
DATABASE_URL=...
STORAGE_BACKEND=r2
# + R2_* para firmar descargas desde la UI
```

## Prueba rápida

```bash
aws lambda invoke \
  --function-name tocheck-reportes-worker \
  --invocation-type Event \
  --payload '{"schemaVersion":1,"jobId":"<UUID-de-un-job-pending-en-Neon>"}' \
  /tmp/out.json
```
