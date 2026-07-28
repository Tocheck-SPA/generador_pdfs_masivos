import { GetObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { awsCredentialsProvider } from "@vercel/oidc-aws-credentials-provider";

export interface ArtifactLocation {
  provider: string | null;
  bucket: string | null;
  key: string;
}

const g = globalThis as unknown as {
  __tocheckR2ArtifactClient?: S3Client;
  __tocheckS3ArtifactClient?: S3Client;
};

export async function presignArtifact(location: ArtifactLocation): Promise<string> {
  const provider = location.provider || process.env.STORAGE_BACKEND || "r2";
  if (provider === "r2") {
    const bucket = location.bucket || required("R2_BUCKET");
    const client = g.__tocheckR2ArtifactClient ??= new S3Client({
      region: process.env.R2_REGION || "auto",
      endpoint: process.env.R2_ENDPOINT ||
        `https://${required("R2_ACCOUNT_ID")}.r2.cloudflarestorage.com`,
      credentials: {
        accessKeyId: required("R2_ACCESS_KEY_ID"),
        secretAccessKey: required("R2_SECRET_ACCESS_KEY"),
      },
    });
    return getSignedUrl(client, new GetObjectCommand({ Bucket: bucket, Key: location.key }), {
      expiresIn: Number(process.env.REPORT_LINK_EXPIRATION_SECONDS || 1_296_000),
    });
  }
  if (provider === "s3") {
    const bucket = location.bucket || required("AWS_S3_BUCKET");
    const roleArn =
      process.env.AWS_S3_ROLE_ARN ||
      process.env.WORKER_AWS_ROLE_ARN ||
      process.env.AWS_ROLE_ARN;
    const client = g.__tocheckS3ArtifactClient ??= new S3Client({
      region:
        process.env.AWS_S3_REGION ||
        process.env.WORKER_AWS_REGION ||
        process.env.AWS_REGION ||
        "us-east-1",
      ...(roleArn
        ? {
            credentials: awsCredentialsProvider({
              roleArn,
              audience: "sts.amazonaws.com",
            }),
          }
        : {}),
    });
    return getSignedUrl(client, new GetObjectCommand({ Bucket: bucket, Key: location.key }), {
      expiresIn: Number(process.env.REPORT_LINK_EXPIRATION_SECONDS || 1_296_000),
    });
  }
  throw new Error(`Proveedor de artefactos no soportado: ${provider}`);
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Falta la variable ${name}.`);
  return value;
}
