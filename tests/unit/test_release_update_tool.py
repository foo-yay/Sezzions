import pytest

from tools.release_update import build_manifest, normalize_version, release_tag


def test_normalize_version_accepts_plain_semver():
    assert normalize_version("1.2.3") == "1.2.3"


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v1.2.3") == "1.2.3"


@pytest.mark.parametrize("value", ["", "1", "1.2", "1.2.beta", "1.2.3.4"])
def test_normalize_version_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        normalize_version(value)


def test_release_tag_uses_normalized_version():
    assert release_tag("v1.0.0") == "v1.0.0"


def test_build_manifest_uses_updates_repo_asset_url():
    manifest = build_manifest(
        version="1.0.1",
        updates_repo="foo-yay/sezzions-updates",
        asset_name="sezzions-macos-arm64.zip",
        asset_sha256="abc123",
        platform_key="macos-arm64",
        notes_url="https://github.com/foo-yay/Sezzions/releases/tag/v1.0.1",
    )

    assert manifest["version"] == "1.0.1"
    assert manifest["notes_url"].endswith("v1.0.1")
    assert manifest["assets"][0]["url"] == (
        "https://github.com/foo-yay/sezzions-updates/releases/download/v1.0.1/"
        "sezzions-macos-arm64.zip"
    )
    assert manifest["assets"][0]["sha256"] == "abc123"
