#!/usr/bin/env bash
# Despliegue QA del worker en sa-east-1 (São Paulo).
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
VERCEL_TEAM_SLUG="TU_TEAM"          # ej. tocheck
VERCEL_PROJECT_NAME="TU_PROYECTO"   # nombre del proyecto en Vercel
VERCEL_ENVIRONMENT="preview"        # o production si QA usa ese env
# Si el OIDC ya existe en la cuenta, descomenta y completa:
# EXISTING_OIDC_ARN="arn:aws:iam::ACCOUNT:oidc-provider/oidc.vercel.com/${VERCEL_TEAM_SLUG}"
EXISTING_OIDC_ARN=""

# Solo fase 2 (secrets / Neon / R2 / Resend de QA)
DATABASE_URL="postgres://USER:PASS@HOST/DB?sslmode=require"
R2_ACCOUNT_ID=""
R2_ACCESS_KEY_ID=""
R2_SECRET_ACCESS_KEY=""
R2_BUCKET=""
R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
RESEND_API_KEY=""
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
  echo "==> Fase 1: ECR + IAM en ${REGION} (sin Lambda aún)"
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
      ImageUri="" \
      "${OIDC_OVERRIDE[@]+"${OIDC_OVERRIDE[@]}"}"

  aws cloudformation describe-stacks \
    --region "${REGION}" \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs" \
    --output table
}

phase2() {
  echo "==> Build + push imagen → ${IMAGE_URI}"
  aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

  docker build -f services/worker/Dockerfile.lambda -t "${IMAGE_URI}" services/worker
  docker push "${IMAGE_URI}"

  echo "==> Fase 2: crear/actualizar Lambda con env de QA"
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
      StorageBackend=r2 \
      R2AccountId="${R2_ACCOUNT_ID}" \
      R2AccessKeyId="${R2_ACCESS_KEY_ID}" \
      R2SecretAccessKey="${R2_SECRET_ACCESS_KEY}" \
      R2Bucket="${R2_BUCKET}" \
      R2Endpoint="${R2_ENDPOINT}" \
      R2Region=auto \
      EmailBackend=resend \
      ResendApiKey="${RESEND_API_KEY}" \
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

  cat <<EOF

Variables Vercel (QA):
  WORKER_DISPATCH_PROVIDER=aws_lambda
  AWS_REGION=${REGION}
  AWS_ROLE_ARN=${ROLE_ARN}
  AWS_LAMBDA_FUNCTION_NAME=${FUNCTION_NAME}

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
