#!/usr/bin/env bash
# Despliegue PROD en us-east-1 — worker (S3+SES) + ingest (RDS).
#   ./infra/aws/deploy-prod.sh phase1|phase2|outputs|ingest1|ingest2

set -euo pipefail

ENV_LABEL="PROD"
REGION="us-east-1"
STACK_NAME="tocheck-reportes-worker-prod"
FUNCTION_NAME="tocheck-reportes-worker-prod"
ECR_REPO="tocheck-reportes-worker-prod"
PROJECT_NAME="tocheck-reportes-prod"
IMAGE_TAG="prod"

# Slug en minúsculas: Vercel OIDC emite iss/sub con "tocheck", no "Tocheck".
VERCEL_TEAM_SLUG="tocheck"
VERCEL_PROJECT_NAME="generador-pdfs-masivos-web"
VERCEL_ENVIRONMENT="production"
EXISTING_OIDC_ARN="arn:aws:iam::668779751312:oidc-provider/oidc.vercel.com/tocheck"

# Completar por entorno
DATABASE_URL=""
STORAGE_BACKEND="s3"
EMAIL_BACKEND="ses"
SES_REGION="us-east-1"
EMAIL_FROM="no-reply@tocheck.cl"
EMAIL_REPLY_TO=""
MEMORY_SIZE_MB="4096"
EPHEMERAL_STORAGE_MB="5120"

INGEST_STACK_NAME="tocheck-reportes-ingest-prod"
INGEST_FUNCTION_NAME="tocheck-reportes-ingest-prod"
INGEST_ECR_REPO="tocheck-reportes-ingest-prod"
INGEST_PROJECT_NAME="tocheck-reportes-ingest-prod"
RDS_HOST=""
RDS_USER=""
RDS_PASS=""
RDS_DB=""
COMPANY_IDS=""
SCHEDULE_EXPRESSION="cron(0 4 * * ? *)"
SCHEDULE_TIMEZONE="America/Santiago"
VPC_SUBNET_IDS=""
VPC_SECURITY_GROUP_IDS=""

# shellcheck source=deploy-common.inc.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/deploy-common.inc.sh"
deploy_dispatch "${1:-}"
