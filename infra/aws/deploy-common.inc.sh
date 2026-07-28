#!/usr/bin/env bash
# Lógica compartida. No ejecutar directo: usar deploy-qa.sh o deploy-prod.sh
# Requiere: ENV_LABEL, REGION, STACK_NAME, FUNCTION_NAME, ECR_REPO, PROJECT_NAME,
# IMAGE_TAG, VERCEL_*, EXISTING_OIDC_ARN, DATABASE_URL, STORAGE_*, EMAIL_*, MEMORY_*,
# INGEST_*, RDS_*, COMPANY_IDS, SCHEDULE_*, y opcional VPC_*

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

_init_aws() {
  ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
  IMAGE_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"
  OIDC_OVERRIDE=()
  if [[ -n "${EXISTING_OIDC_ARN:-}" ]]; then
    OIDC_OVERRIDE+=(ExistingOidcProviderArn="${EXISTING_OIDC_ARN}")
  fi
}

phase1() {
  _init_aws
  echo "==> [${ENV_LABEL}] Fase 1: ECR + S3 + IAM en ${REGION} (sin Lambda aún)"
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
      SesRegion="${SES_REGION}" \
      EmailFrom="${EMAIL_FROM}" \
      MemorySizeMB="${MEMORY_SIZE_MB}" \
      EphemeralStorageMB="${EPHEMERAL_STORAGE_MB}" \
      ImageUri="" \
      "${OIDC_OVERRIDE[@]+"${OIDC_OVERRIDE[@]}"}"

  outputs
}

phase2() {
  _init_aws
  echo "==> [${ENV_LABEL}] Build + push imagen → ${IMAGE_URI}"
  aws ecr get-login-password --region "${REGION}" \
    | "${DOCKER[@]}" login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

  "${DOCKER[@]}" build \
    --platform linux/amd64 \
    --provenance=false \
    --sbom=false \
    -f services/worker/Dockerfile.lambda \
    -t "${IMAGE_URI}" \
    services/worker
  "${DOCKER[@]}" push "${IMAGE_URI}"

  echo "==> [${ENV_LABEL}] Fase 2: Lambda worker (S3 + SES)"
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
      MemorySizeMB="${MEMORY_SIZE_MB}" \
      EphemeralStorageMB="${EPHEMERAL_STORAGE_MB}" \
      "${OIDC_OVERRIDE[@]+"${OIDC_OVERRIDE[@]}"}"

  outputs
}

outputs() {
  _init_aws
  echo "==> [${ENV_LABEL}] Outputs (pegar en Vercel)"
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

Variables Vercel (${ENV_LABEL}):
  WORKER_DISPATCH_PROVIDER=aws_lambda
  WORKER_AWS_REGION=${REGION}
  WORKER_AWS_ROLE_ARN=${ROLE_ARN}
  WORKER_LAMBDA_FUNCTION_NAME=${FUNCTION_NAME}
  STORAGE_BACKEND=s3
  AWS_S3_BUCKET=${BUCKET}
  AWS_S3_REGION=${REGION}
  # Fallback si OIDC falla:
  # WORKER_AWS_ACCESS_KEY_ID=...
  # WORKER_AWS_SECRET_ACCESS_KEY=...

Rebuild rápido (tag :${IMAGE_TAG}):
  aws ecr get-login-password --region ${REGION} \\
    | ${DOCKER[*]} login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com
  ${DOCKER[*]} build --platform linux/amd64 --provenance=false --sbom=false \\
    -f services/worker/Dockerfile.lambda -t ${IMAGE_URI} services/worker
  ${DOCKER[*]} push ${IMAGE_URI}
  aws lambda update-function-code --region ${REGION} \\
    --function-name ${FUNCTION_NAME} --image-uri ${IMAGE_URI}

Prueba invoke:
  aws lambda invoke --region ${REGION} --function-name ${FUNCTION_NAME} \\
    --invocation-type Event --cli-binary-format raw-in-base64-out \\
    --payload '{"schemaVersion":1,"jobId":"<UUID>"}' /tmp/out.json

Probe Chromium:
  aws lambda invoke --region ${REGION} --function-name ${FUNCTION_NAME} \\
    --cli-binary-format raw-in-base64-out \\
    --payload '{"debug":"chromium"}' /tmp/chromium-probe.json && cat /tmp/chromium-probe.json
EOF
}

ingest1() {
  _init_aws
  echo "==> [${ENV_LABEL}] Ingest fase 1: ECR en ${REGION}"
  aws cloudformation deploy \
    --region "${REGION}" \
    --template-file infra/aws/ingest-lambda.yaml \
    --stack-name "${INGEST_STACK_NAME}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      ProjectName="${INGEST_PROJECT_NAME}" \
      FunctionName="${INGEST_FUNCTION_NAME}" \
      EcrRepositoryName="${INGEST_ECR_REPO}" \
      ImageUri=""
}

ingest2() {
  _init_aws
  local ingest_image="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${INGEST_ECR_REPO}:${IMAGE_TAG}"
  echo "==> [${ENV_LABEL}] Build + push ingest → ${ingest_image}"
  aws ecr get-login-password --region "${REGION}" \
    | "${DOCKER[@]}" login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

  "${DOCKER[@]}" build \
    --platform linux/amd64 \
    --provenance=false \
    --sbom=false \
    -f services/worker/Dockerfile.ingest \
    -t "${ingest_image}" \
    services/worker
  "${DOCKER[@]}" push "${ingest_image}"

  local vpc_overrides=()
  if [[ -n "${VPC_SUBNET_IDS:-}" ]]; then
    vpc_overrides+=(VpcSubnetIds="${VPC_SUBNET_IDS}")
  fi
  if [[ -n "${VPC_SECURITY_GROUP_IDS:-}" ]]; then
    vpc_overrides+=(VpcSecurityGroupIds="${VPC_SECURITY_GROUP_IDS}")
  fi

  echo "==> [${ENV_LABEL}] Ingest fase 2: Lambda + schedule en ${REGION}"
  aws cloudformation deploy \
    --region "${REGION}" \
    --template-file infra/aws/ingest-lambda.yaml \
    --stack-name "${INGEST_STACK_NAME}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
      ProjectName="${INGEST_PROJECT_NAME}" \
      FunctionName="${INGEST_FUNCTION_NAME}" \
      EcrRepositoryName="${INGEST_ECR_REPO}" \
      ImageUri="${ingest_image}" \
      DatabaseUrl="${DATABASE_URL}" \
      RdsHost="${RDS_HOST}" \
      RdsUser="${RDS_USER}" \
      RdsPass="${RDS_PASS}" \
      RdsDb="${RDS_DB}" \
      CompanyIds="${COMPANY_IDS}" \
      ScheduleExpression="${SCHEDULE_EXPRESSION}" \
      ScheduleTimezone="${SCHEDULE_TIMEZONE}" \
      "${vpc_overrides[@]+"${vpc_overrides[@]}"}"

  cat <<EOF

Prueba ingest:
  aws lambda invoke --region ${REGION} --function-name ${INGEST_FUNCTION_NAME} \\
    --cli-binary-format raw-in-base64-out \\
    --payload '{"schemaVersion":1,"companyIds":"${COMPANY_IDS}","lookbackDays":7}' \\
    /tmp/ingest-out.json && cat /tmp/ingest-out.json
EOF
}

deploy_dispatch() {
  case "${1:-}" in
    phase1) phase1 ;;
    phase2) phase2 ;;
    outputs) outputs ;;
    ingest1) ingest1 ;;
    ingest2) ingest2 ;;
    *)
      echo "Uso: $0 phase1|phase2|outputs|ingest1|ingest2"
      exit 1
      ;;
  esac
}
