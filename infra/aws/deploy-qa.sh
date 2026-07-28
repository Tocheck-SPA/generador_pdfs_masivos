#!/usr/bin/env bash
# Despliegue QA del worker en sa-east-1 (São Paulo) — S3 + SES.
# Uso:
#   1) Completa las variables de la sección CONFIG
#   2) Fase 1:  ./infra/aws/deploy-qa.sh phase1
#   3) Fase 2:  ./infra/aws/deploy-qa.sh phase2
#   4) Outputs: ./infra/aws/deploy-qa.sh outputs

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# ---------- CONFIG (completar) ----------
REGION="sa-east-1"
STACK_NAME="tocheck-reportes-worker-qa"
FUNCTION_NAME="tocheck-reportes-worker-qa"
ECR_REPO="tocheck-reportes-worker-qa"
PROJECT_NAME="tocheck-reportes-qa"

# Vercel QA
VERCEL_TEAM_SLUG="Tocheck"
VERCEL_PROJECT_NAME="generador-pdfs-masivos-web"
VERCEL_ENVIRONMENT="production"
EXISTING_OIDC_ARN="arn:aws:iam::668779751312:oidc-provider/oidc.vercel.com/Tocheck"

# Solo fase 2
DATABASE_URL="postgres://USER:PASS@HOST/DB?sslmode=require"
STORAGE_BACKEND="s3"
EMAIL_BACKEND="ses"
SES_REGION="sa-east-1"
EMAIL_FROM="reportes@tocheck.cl"
EMAIL_REPLY_TO=""
# ----------------------------------------

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
IMAGE_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:qa"

OIDC_OVERRIDE=()
if [[ -n "${EXISTING_OIDC_ARN}" ]]; then
  OIDC_OVERRIDE+=(ExistingOidcProviderArn="${EXISTING_OIDC_ARN}")
fi

phase1() {
  echo "==> Fase 1: ECR + S3 + IAM en ${REGION} (sin Lambda aún)"
  aws cloudformation deploy \
    --region "${REGION}" \
    --template-file infra/aws/worker-lambda.yaml \
    --stack-name "${STACK_NAME}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      ProjectName="${PROJECT_NAME}" \
      FunctionName="${FUNCTION_NAME}" \
      EcrRepositoryName="${ECR_REPO}" \
      VercelTeamSlug="${VERCEL_TEAM_SLUG}" \
      VercelProjectName="${VERCEL_PROJECT_NAME}" \
      VercelEnvironment="${VERCEL_ENVIRONMENT}" \
      StorageBackend="${STORAGE_BACKEND}" \
      EmailBackend="${EMAIL_BACKEND}" \
      ImageUri="" \
      "${OIDC_OVERRIDE[@]+"${OIDC_OVERRIDE[@]}"}"

  outputs
}

phase2() {
  echo "==> Build + push imagen → ${IMAGE_URI}"
  aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

  docker build -f services/worker/Dockerfile.lambda -t "${IMAGE_URI}" services/worker
  docker push "${IMAGE_URI}"

  echo "==> Fase 2: crear/actualizar Lambda con env de QA (S3 + SES)"
  aws cloudformation deploy \
    --region "${REGION}" \
    --template-file infra/aws/worker-lambda.yaml \
    --stack-name "${STACK_NAME}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      ProjectName="${PROJECT_NAME}" \
      FunctionName="${FUNCTION_NAME}" \
      EcrRepositoryName="${ECR_REPO}" \
      VercelTeamSlug="${VERCEL_TEAM_SLUG}" \
      VercelProjectName="${VERCEL_PROJECT_NAME}" \
      VercelEnvironment="${VERCEL_ENVIRONMENT}" \
      ImageUri="${IMAGE_URI}" \
      DatabaseUrl="${DATABASE_URL}" \
      SourceAdapter=snapshot \
      StorageBackend="${STORAGE_BACKEND}" \
      EmailBackend="${EMAIL_BACKEND}" \
      SesRegion="${SES_REGION}" \
      EmailFrom="${EMAIL_FROM}" \
      EmailReplyTo="${EMAIL_REPLY_TO}" \
      "${OIDC_OVERRIDE[@]+"${OIDC_OVERRIDE[@]}"}"

  outputs
}

outputs() {
  echo "==> Outputs (pegar en Vercel QA)"
  aws cloudformation describe-stacks \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs" \
    --output table

  ROLE_ARN="$(aws cloudformation describe-stacks \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='VercelInvokeRoleArn'].OutputValue" \
    --output text)"
  BUCKET="$(aws cloudformation describe-stacks \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='ArtifactsBucketName'].OutputValue" \
    --output text)"

  cat <<EOF

Variables Vercel (QA):
  WORKER_DISPATCH_PROVIDER=aws_lambda
  AWS_REGION=${REGION}
  AWS_ROLE_ARN=${ROLE_ARN}
  AWS_LAMBDA_FUNCTION_NAME=${FUNCTION_NAME}
  STORAGE_BACKEND=s3
  AWS_S3_BUCKET=${BUCKET}
  AWS_S3_REGION=${REGION}

Prueba invoke (job pending en Neon QA):
  aws lambda invoke \\
    --region ${REGION} \\
    --function-name ${FUNCTION_NAME} \\
    --invocation-type Event \\
    --cli-binary-format raw-in-base64-out \\
    --payload '{"schemaVersion":1,"jobId":"<UUID>"}' \\
    /tmp/out.json
EOF
}

case "${1:-}" in
  phase1) phase1 ;;
  phase2) phase2 ;;
  outputs) outputs ;;
  *)
    echo "Uso: $0 phase1|phase2|outputs"
    exit 1
    ;;
esac
