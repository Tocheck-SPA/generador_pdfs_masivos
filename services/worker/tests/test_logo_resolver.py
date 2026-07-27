from __future__ import annotations

from app.reports.images import _resolve_logo
from app.source.models import SourceAsset


class CapturingRepository:
    def __init__(self):
        self.paths: list[str] = []

    def resolve_asset(self, path: str) -> SourceAsset:
        self.paths.append(path)
        return SourceAsset(path=path, found=False)


def test_company_logo_uses_separate_public_base():
    repo = CapturingRepository()

    assert _resolve_logo(
        "254_logo.png",
        repo,
        "https://app.tocheck.cl/public/upload/files/logo_empresa",
    ) is None
    assert repo.paths == [
        "https://app.tocheck.cl/public/upload/files/logo_empresa/254_logo.png"
    ]
