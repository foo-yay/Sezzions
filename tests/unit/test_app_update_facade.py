from pathlib import Path

from app_facade import AppFacade


def test_check_for_app_updates_returns_dict(tmp_path):
    db_path = tmp_path / "app.db"
    facade = AppFacade(str(db_path))
    manifest_url = "https://example.com/latest.json"
    manifest_bytes = b'{"version":"9.9.9","notes_url":"https://example.com/notes","assets":[{"platform":"macos-arm64","url":"https://example.com/sezzions.dmg","sha256":"abc"}]}'

    facade.update_service.platform_key = "macos-arm64"
    facade.update_service.fetcher = lambda url, timeout=10: manifest_bytes

    result = facade.check_for_app_updates(manifest_url=manifest_url)

    assert result["update_available"] is True
    assert result["latest_version"] == "9.9.9"
    assert result["asset"]["url"] == "https://example.com/sezzions.dmg"

    facade.db.close()


def test_download_app_update_downloads_and_verifies(tmp_path):
    db_path = tmp_path / "app.db"
    facade = AppFacade(str(db_path))
    payload = b"abc"
    expected_sha = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    facade.update_service.fetcher = lambda url, timeout=10: payload

    file_path = facade.download_app_update(
        {
            "platform": "macos-arm64",
            "url": "https://example.com/sezzions.dmg",
            "sha256": expected_sha,
            "name": "sezzions.dmg",
        },
        destination_dir=str(tmp_path),
    )

    assert Path(file_path).exists()
    assert Path(file_path).read_bytes() == payload

    facade.db.close()
