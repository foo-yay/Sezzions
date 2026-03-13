import pytest
import tools.release_update as release_update
import json

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


def test_default_updates_repo_points_to_sezzions_repo():
    assert release_update.DEFAULT_UPDATES_REPO == "foo-yay/sezzions-updates"


def test_ensure_updates_repo_is_separate_allows_split_repos():
    release_update.ensure_updates_repo_is_separate("foo-yay/Sezzions", "foo-yay/sezzions-updates")


def test_ensure_updates_repo_is_separate_rejects_same_repo():
    with pytest.raises(RuntimeError, match="must be separate"):
        release_update.ensure_updates_repo_is_separate("foo-yay/Sezzions", "foo-yay/Sezzions")


def test_build_manifest_uses_updates_repo_asset_url():
    manifest = build_manifest(
        version="1.0.1",
        updates_repo="foo-yay/sezzions-updates",
        assets=[
            {
                "platform": "macos-arm64",
                "name": "sezzions-macos-arm64.zip",
                "sha256": "abc123",
            }
        ],
        notes_url="https://github.com/foo-yay/Sezzions/releases/tag/v1.0.1",
    )

    assert manifest["version"] == "1.0.1"
    assert manifest["notes_url"].endswith("v1.0.1")
    assert manifest["assets"][0]["url"] == (
        "https://github.com/foo-yay/sezzions-updates/releases/download/v1.0.1/"
        "sezzions-macos-arm64.zip"
    )
    assert manifest["assets"][0]["sha256"] == "abc123"


def test_build_manifest_supports_multiple_platform_assets():
    manifest = build_manifest(
        version="1.0.1",
        updates_repo="foo-yay/sezzions-updates",
        assets=[
            {
                "platform": "macos-arm64",
                "name": "sezzions-macos-arm64.zip",
                "sha256": "macsha",
            },
            {
                "platform": "windows-x64",
                "name": "sezzions-windows-x64.zip",
                "sha256": "winsha",
            },
        ],
        notes_url="https://github.com/foo-yay/sezzions-updates/releases/tag/v1.0.1",
    )

    assert len(manifest["assets"]) == 2
    assert manifest["assets"][1]["platform"] == "windows-x64"
    assert manifest["assets"][1]["url"].endswith("/sezzions-windows-x64.zip")


def test_parse_extra_asset_spec_accepts_platform_equals_path():
    platform_key, asset_path = release_update.parse_extra_asset_spec(
        "windows-x64=/tmp/sezzions-windows-x64.zip"
    )

    assert platform_key == "windows-x64"
    assert str(asset_path).endswith("sezzions-windows-x64.zip")


@pytest.mark.parametrize("value", ["", "windows-x64", "=/tmp/file.zip", "windows-x64="])
def test_parse_extra_asset_spec_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="extra-asset"):
        release_update.parse_extra_asset_spec(value)


def test_bump_patch_version_increments_patch_component():
    assert release_update.bump_patch_version("1.0.0") == "1.0.1"


def test_pick_highest_version_prefers_newer_release_version():
    assert release_update.pick_highest_version("1.0.0", "1.0.1") == "1.0.1"


def test_pick_highest_version_keeps_local_when_newer():
    assert release_update.pick_highest_version("1.0.2", "1.0.1") == "1.0.2"


def test_read_latest_release_version_parses_tag(monkeypatch: pytest.MonkeyPatch):
    class _Result:
        returncode = 0
        stdout = json.dumps({"tagName": "v1.0.9"})

    monkeypatch.setattr(release_update.subprocess, "run", lambda *args, **kwargs: _Result())

    assert release_update.read_latest_release_version("foo-yay/sezzions-updates") == "1.0.9"


def test_read_latest_release_version_returns_none_on_missing_release(monkeypatch: pytest.MonkeyPatch):
    class _Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(release_update.subprocess, "run", lambda *args, **kwargs: _Result())

    assert release_update.read_latest_release_version("foo-yay/sezzions-updates") is None


def test_ensure_local_version_not_behind_allows_equal_version():
    release_update.ensure_local_version_not_behind("1.0.2", "1.0.2")


def test_ensure_local_version_not_behind_allows_newer_local_version():
    release_update.ensure_local_version_not_behind("1.0.3", "1.0.2")


def test_ensure_local_version_not_behind_raises_when_local_is_older():
    with pytest.raises(RuntimeError, match="behind"):
        release_update.ensure_local_version_not_behind("1.0.0", "1.0.2")


def test_read_repo_version_reads_semver(tmp_path):
    version_file = tmp_path / "__init__.py"
    version_file.write_text('__version__ = "2.3.4"\n', encoding="utf-8")

    assert release_update.read_repo_version(version_file) == "2.3.4"


def test_write_repo_version_updates_semver(tmp_path):
    version_file = tmp_path / "__init__.py"
    version_file.write_text('__version__ = "2.3.4"\n', encoding="utf-8")

    release_update.write_repo_version(version_file, "2.3.5", dry_run=False)

    assert '__version__ = "2.3.5"' in version_file.read_text(encoding="utf-8")


def test_write_repo_version_dry_run_leaves_file_unchanged(tmp_path):
    version_file = tmp_path / "__init__.py"
    original_content = '__version__ = "3.0.0"\n'
    version_file.write_text(original_content, encoding="utf-8")

    release_update.write_repo_version(version_file, "3.0.1", dry_run=True)

    assert version_file.read_text(encoding="utf-8") == original_content


def test_sync_local_branch_raises_if_worktree_dirty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(release_update, "_git_current_branch", lambda: "feature/x")
    monkeypatch.setattr(release_update, "_git_status_porcelain", lambda: " M tools/release_update.py")

    with pytest.raises(RuntimeError, match="uncommitted changes"):
        release_update.sync_local_branch("main", dry_run=False)


def test_sync_local_branch_switches_then_pulls(monkeypatch: pytest.MonkeyPatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(release_update, "_git_current_branch", lambda: "feature/174-release-automation")
    monkeypatch.setattr(release_update, "_git_status_porcelain", lambda: "")

    def _record(command: list[str], dry_run: bool = False) -> None:
        commands.append(command)

    monkeypatch.setattr(release_update, "run_command", _record)

    release_update.sync_local_branch("main", dry_run=False)

    assert commands == [
        ["git", "fetch", "origin", "main"],
        ["git", "checkout", "main"],
        ["git", "pull", "--ff-only", "origin", "main"],
    ]


def test_sync_local_branch_skips_checkout_if_already_on_target(monkeypatch: pytest.MonkeyPatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(release_update, "_git_current_branch", lambda: "main")
    monkeypatch.setattr(release_update, "_git_status_porcelain", lambda: "")

    def _record(command: list[str], dry_run: bool = False) -> None:
        commands.append(command)

    monkeypatch.setattr(release_update, "run_command", _record)

    release_update.sync_local_branch("main", dry_run=False)

    assert commands == [
        ["git", "fetch", "origin", "main"],
        ["git", "pull", "--ff-only", "origin", "main"],
    ]


def test_build_macos_artifact_includes_resources_data(monkeypatch: pytest.MonkeyPatch):
    commands: list[list[str]] = []

    monkeypatch.setattr(release_update.host_platform, "system", lambda: "Darwin")

    def _record(command: list[str], dry_run: bool = False) -> None:
        commands.append(command)

    monkeypatch.setattr(release_update, "run_command", _record)

    output = release_update.build_macos_artifact(
        binary_basename="sezzions-macos-arm64",
        app_entrypoint="sezzions.py",
        dry_run=True,
    )

    assert output.as_posix().endswith("dist/sezzions-macos-arm64.app")
    assert len(commands) == 1
    assert "--add-data" in commands[0]
    add_data_index = commands[0].index("--add-data")
    assert commands[0][add_data_index + 1] == "resources:resources"
