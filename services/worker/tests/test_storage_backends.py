from __future__ import annotations

from types import SimpleNamespace


class FakeS3Client:
    def __init__(self):
        self.objects = {}

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs["Body"]

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        return f"https://signed.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}


def test_s3_storage_implements_storage_contract(monkeypatch):
    import boto3

    fake = FakeS3Client()
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: fake)

    from app.storage.s3_storage import S3Storage

    storage = S3Storage(bucket="reports", region="us-east-1")
    stored = storage.put("reports/test.zip", b"zip", "application/zip")

    assert stored.storage_provider == "s3"
    assert stored.storage_bucket == "reports"
    assert storage.exists("reports/test.zip")
    assert storage.presigned_url("reports/test.zip", 60).startswith("https://signed.example/")


def test_lambda_handler_validates_and_targets_job(monkeypatch):
    from app import lambda_handler

    called = {}
    monkeypatch.setattr(lambda_handler, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        lambda_handler,
        "run_worker_job",
        lambda settings, job_id, worker_id=None: called.update(
            {"job_id": job_id, "worker_id": worker_id}
        ) or True,
    )

    result = lambda_handler.handler(
        {"schemaVersion": 1, "jobId": "550e8400-e29b-41d4-a716-446655440000"},
        SimpleNamespace(aws_request_id="req-1"),
    )

    assert result["processed"] is True
    assert called == {
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
        "worker_id": "lambda:req-1",
    }
