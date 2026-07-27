from __future__ import annotations

import httpx

from app.source.asset_resolver import resolve_remote_asset


def test_relative_source_path_uses_public_s3_base(monkeypatch):
    calls: list[str] = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def get(self, url: str):
            calls.append(url)
            return httpx.Response(
                200,
                headers={"content-type": "image/jpeg"},
                content=b"jpeg-bytes",
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr("app.source.asset_resolver.httpx.Client", FakeClient)

    asset = resolve_remote_asset(
        "/imagenes_checklist/254/2097/chk_2097_45091_1_1783541733515.jpg",
        asset_base_url="https://tocheck.s3.amazonaws.com/",
    )

    assert calls == [
        "https://tocheck.s3.amazonaws.com/imagenes_checklist/254/2097/"
        "chk_2097_45091_1_1783541733515.jpg"
    ]
    assert asset.found is True
    assert asset.content == b"jpeg-bytes"
    assert asset.content_type == "image/jpeg"
