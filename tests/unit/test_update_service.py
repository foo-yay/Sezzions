from pathlib import Path

from services.update_service import UpdateAsset, UpdateService


def _make_fetcher(payloads: dict[str, bytes]):
    def _fetch(url: str, timeout: int = 10) -> bytes:
        return payloads[url]

    return _fetch


def test_check_for_updates_returns_available_with_platform_asset():
    manifest_url = "https://example.com/latest.json"
    manifest_bytes = b'{"version":"1.2.0","published_at":"2026-03-12T00:00:00Z","notes_url":"https://example.com/release-notes","assets":[{"platform":"macos-arm64","url":"https://example.com/sezzions-1.2.0.dmg","sha256":"abc123"}]}'
    service = UpdateService(
        current_version="1.1.9",
        manifest_url=manifest_url,
        platform_key="macos-arm64",
        fetcher=_make_fetcher({manifest_url: manifest_bytes}),
    )

    result = service.check_for_updates()

    assert result.update_available is True
    assert result.latest_version == "1.2.0"
    assert result.asset is not None
    assert result.asset.url == "https://example.com/sezzions-1.2.0.dmg"


def test_check_for_updates_returns_up_to_date_when_latest_not_newer():
    manifest_url = "https://example.com/latest.json"
    manifest_bytes = b'{"version":"1.2.0","assets":[]}'
    service = UpdateService(
        current_version="1.2.0",
        manifest_url=manifest_url,
        platform_key="macos-arm64",
        fetcher=_make_fetcher({manifest_url: manifest_bytes}),
    )

    result = service.check_for_updates()

    assert result.update_available is False
    assert result.latest_version == "1.2.0"
    assert result.error is None


def test_check_for_updates_reports_error_when_manifest_is_invalid():
    manifest_url = "https://example.com/latest.json"
    bad_bytes = b'{"assets":[]}'
    service = UpdateService(
        current_version="1.0.0",
        manifest_url=manifest_url,
        platform_key="macos-arm64",
        fetcher=_make_fetcher({manifest_url: bad_bytes}),
    )

    result = service.check_for_updates()

    assert result.update_available is False
    assert result.error is not None


def test_download_and_verify_writes_file_and_validates_sha256(tmp_path):
    payload = b"sezzions-update-binary"
    expected_sha = "1a1d8a78478146064ab4ec86ffd8707cc545b25ecd55c5b699db93cd4d0745eb"
    asset = UpdateAsset(
        platform="macos-arm64",
        url="https://example.com/sezzions.dmg",
        sha256=expected_sha,
        name="sezzions.dmg",
    )
    service = UpdateService(
        current_version="1.0.0",
        manifest_url="https://example.com/latest.json",
        platform_key="macos-arm64",
        fetcher=_make_fetcher({asset.url: payload}),
    )

    file_path = service.download_and_verify(asset, tmp_path)

    assert Path(file_path).exists()
    assert Path(file_path).read_bytes() == payload


def test_download_and_verify_raises_on_checksum_mismatch(tmp_path):
    payload = b"different-binary"
    asset = UpdateAsset(
        platform="macos-arm64",
        url="https://example.com/sezzions.dmg",
        sha256="0" * 64,
        name="sezzions.dmg",
    )
    service = UpdateService(
        current_version="1.0.0",
        manifest_url="https://example.com/latest.json",
        platform_key="macos-arm64",
        fetcher=_make_fetcher({asset.url: payload}),
    )

    try:
        service.download_and_verify(asset, tmp_path)
        assert False, "Expected checksum mismatch"
    except ValueError as exc:
        assert "Checksum mismatch" in str(exc)
