from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform as host_platform
import re
import shutil
import subprocess
import sys
from typing import Any


DEFAULT_SOURCE_REPO = "foo-yay/Sezzions"
DEFAULT_UPDATES_REPO = "foo-yay/sezzions-updates"
DEFAULT_PLATFORM_KEY = "macos-arm64"
DEFAULT_BINARY_BASENAME = "sezzions-macos-arm64"
DEFAULT_MACOS_DISPLAY_NAME = "Sezzions"
DEFAULT_VERSION_FILE = "__init__.py"


def _normalize_repo_name(repo: str) -> str:
    return (repo or "").strip().lower()


def ensure_updates_repo_is_separate(source_repo: str, updates_repo: str) -> None:
    if _normalize_repo_name(source_repo) == _normalize_repo_name(updates_repo):
        raise RuntimeError(
            "Updates repo must be separate from source repo. "
            "Publish updater binaries/manifest to foo-yay/sezzions-updates."
        )


def normalize_version(version: str) -> str:
    value = (version or "").strip()
    if value.lower().startswith("v"):
        value = value[1:]

    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("Version must be semantic format X.Y.Z (for example 1.0.1)")
    return value


def release_tag(version: str) -> str:
    return f"v{normalize_version(version)}"


def bump_patch_version(version: str) -> str:
    major, minor, patch = normalize_version(version).split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def _version_tuple(version: str) -> tuple[int, int, int]:
    major, minor, patch = normalize_version(version).split(".")
    return int(major), int(minor), int(patch)


def pick_highest_version(a: str, b: str | None) -> str:
    base_a = normalize_version(a)
    if not b:
        return base_a
    base_b = normalize_version(b)
    return base_b if _version_tuple(base_b) > _version_tuple(base_a) else base_a


def ensure_local_version_not_behind(local_version: str, published_version: str | None) -> None:
    if not published_version:
        return

    local_normalized = normalize_version(local_version)
    published_normalized = normalize_version(published_version)
    if _version_tuple(local_normalized) < _version_tuple(published_normalized):
        raise RuntimeError(
            "Local source version is behind latest published updates release "
            f"({local_normalized} < {published_normalized}). "
            "Update __version__ before publishing."
        )


def read_latest_release_version(repo: str) -> str | None:
    result = subprocess.run(
        ["gh", "release", "view", "--repo", repo, "--json", "tagName"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    payload = json.loads(result.stdout or "{}")
    tag = payload.get("tagName")
    if not tag:
        return None
    return normalize_version(str(tag))


def read_repo_version(version_file: Path) -> str:
    if not version_file.exists():
        raise FileNotFoundError(f"Version file not found: {version_file}")

    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([0-9]+\.[0-9]+\.[0-9]+)["\']', content)
    if not match:
        raise ValueError(
            f"Could not find __version__ semantic value in {version_file}"
        )
    return normalize_version(match.group(1))


def write_repo_version(version_file: Path, version: str, dry_run: bool = False) -> None:
    normalized = normalize_version(version)
    content = version_file.read_text(encoding="utf-8")
    updated_content, count = re.subn(
        r'(__version__\s*=\s*["\'])([0-9]+\.[0-9]+\.[0-9]+)(["\'])',
        rf"\g<1>{normalized}\g<3>",
        content,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not update __version__ in {version_file}")

    print(f"Updating {version_file} to version {normalized}")
    if dry_run:
        return
    version_file.write_text(updated_content, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    version: str,
    updates_repo: str,
    assets: list[dict[str, str]],
    notes_url: str,
) -> dict[str, Any]:
    tag = release_tag(version)
    return {
        "version": normalize_version(version),
        "published_at": "",  # Filled by release timestamp at upload time if needed
        "notes_url": notes_url,
        "assets": [
            {
                "platform": asset["platform"],
                "url": f"https://github.com/{updates_repo}/releases/download/{tag}/{asset['name']}",
                "sha256": asset["sha256"],
                "name": asset["name"],
            }
            for asset in assets
        ],
    }


def parse_extra_asset_spec(spec: str) -> tuple[str, Path]:
    value = (spec or "").strip()
    if "=" not in value:
        raise ValueError(
            "Invalid --extra-asset value. Use format PLATFORM=/path/to/asset.zip"
        )

    platform_key, path_value = value.split("=", 1)
    platform_key = platform_key.strip()
    path_value = path_value.strip()
    if not platform_key or not path_value:
        raise ValueError(
            "Invalid --extra-asset value. Use format PLATFORM=/path/to/asset.zip"
        )
    return platform_key, Path(path_value)


def run_command(command: list[str], dry_run: bool = False) -> None:
    printable = " ".join(command)
    print(f"$ {printable}")
    if dry_run:
        return
    subprocess.run(command, check=True)


def _run_capture(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return (result.stdout or "").strip()


def _git_status_porcelain() -> str:
    return _run_capture(["git", "status", "--porcelain"])


def _git_current_branch() -> str:
    return _run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def sync_local_branch(branch: str, dry_run: bool = False) -> None:
    current_branch = _git_current_branch()
    if not dry_run and _git_status_porcelain():
        raise RuntimeError(
            "Cannot sync local branch with uncommitted changes present. "
            "Commit or stash your work, then run release again."
        )

    run_command(["git", "fetch", "origin", branch], dry_run=dry_run)
    if current_branch != branch:
        run_command(["git", "checkout", branch], dry_run=dry_run)
    run_command(["git", "pull", "--ff-only", "origin", branch], dry_run=dry_run)

    if current_branch != branch:
        print(
            f"Synced local branch '{branch}' (previous branch was '{current_branch}')."
        )


def release_exists(repo: str, tag: str) -> bool:
    result = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def ensure_updates_release(repo: str, tag: str, dry_run: bool) -> None:
    if release_exists(repo, tag):
        return

    run_command(
        [
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--title",
            f"Sezzions Updates {tag}",
            "--notes",
            f"Public updater assets for Sezzions {tag}",
        ],
        dry_run=dry_run,
    )


def build_macos_artifact(binary_basename: str, app_entrypoint: str, dry_run: bool) -> Path:
    if host_platform.system().lower() != "darwin":
        raise RuntimeError("This build script currently supports macOS artifact creation only.")

    run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--name",
            binary_basename,
            "--windowed",
            "--add-data",
            "resources:resources",
            app_entrypoint,
        ],
        dry_run=dry_run,
    )

    info_plist_path = Path("dist") / f"{binary_basename}.app" / "Contents" / "Info.plist"
    run_command(
        [
            "/usr/libexec/PlistBuddy",
            "-c",
            f"Set :CFBundleName {DEFAULT_MACOS_DISPLAY_NAME}",
            str(info_plist_path),
        ],
        dry_run=dry_run,
    )
    run_command(
        [
            "/usr/libexec/PlistBuddy",
            "-c",
            f"Set :CFBundleDisplayName {DEFAULT_MACOS_DISPLAY_NAME}",
            str(info_plist_path),
        ],
        dry_run=dry_run,
    )
    run_command(
        [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            "-",
            str(Path("dist") / f"{binary_basename}.app"),
        ],
        dry_run=dry_run,
    )

    return Path("dist") / f"{binary_basename}.app"


def zip_macos_app(app_bundle_path: Path, zip_output_path: Path, dry_run: bool) -> None:
    if not dry_run and not app_bundle_path.exists():
        raise FileNotFoundError(f"Expected app bundle not found: {app_bundle_path}")

    zip_output_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app_bundle_path),
            str(zip_output_path),
        ],
        dry_run=dry_run,
    )


def write_manifest_file(manifest_path: Path, manifest: dict[str, Any], dry_run: bool) -> None:
    print(f"Writing manifest: {manifest_path}")
    if dry_run:
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and publish Sezzions update assets.")
    version_group = parser.add_mutually_exclusive_group(required=True)
    version_group.add_argument("--version", help="Semantic version, e.g. 1.0.1")
    version_group.add_argument(
        "--next-patch",
        action="store_true",
        help="Increment patch version from __version__ in --version-file.",
    )
    version_group.add_argument(
        "--check-version-sync",
        action="store_true",
        help="Validate local __version__ is not behind latest published updates release.",
    )
    parser.add_argument(
        "--version-file",
        default=DEFAULT_VERSION_FILE,
        help="Path to file containing __version__ assignment (default: __init__.py).",
    )
    parser.add_argument("--source-repo", default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--updates-repo", default=DEFAULT_UPDATES_REPO)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM_KEY)
    parser.add_argument("--binary-basename", default=DEFAULT_BINARY_BASENAME)
    parser.add_argument("--app-entrypoint", default="sezzions.py")
    parser.add_argument("--asset-name", default="sezzions-macos-arm64.zip")
    parser.add_argument("--asset-path", default="", help="Use an existing zip file instead of building.")
    parser.add_argument(
        "--extra-asset",
        action="append",
        default=[],
        help=(
            "Additional prebuilt asset mapping in format PLATFORM=/path/to/asset.zip. "
            "Repeat for multiple assets (for example windows-x64=...)."
        ),
    )
    parser.add_argument(
        "--release-dir",
        default="release",
        help="Directory where generated release assets are staged.",
    )
    parser.add_argument(
        "--publish-source-release",
        action="store_true",
        help="Also create a source-repo GitHub release tag if missing.",
    )
    parser.add_argument(
        "--sync-local-main",
        action="store_true",
        help="After release publish, switch/sync local checkout to up-to-date main.",
    )
    parser.add_argument(
        "--sync-branch",
        default="main",
        help="Branch name used by --sync-local-main (default: main).",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_updates_repo_is_separate(args.source_repo, args.updates_repo)
    version_file = Path(args.version_file)
    latest_published_version = read_latest_release_version(args.updates_repo)

    if args.check_version_sync:
        local_version = read_repo_version(version_file)
        ensure_local_version_not_behind(local_version, latest_published_version)
        print(
            "Version sync check passed: "
            f"local={local_version}, latest_published={latest_published_version or 'none'}"
        )
        return 0

    if args.next_patch:
        current_version = read_repo_version(version_file)
        base_version = pick_highest_version(current_version, latest_published_version)
        version = bump_patch_version(base_version)
        write_repo_version(version_file, version, dry_run=args.dry_run)
    else:
        version = normalize_version(args.version)

    ensure_local_version_not_behind(version, latest_published_version)
    tag = release_tag(version)

    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI (gh) is required on PATH.")

    staged_release_dir = Path(args.release_dir) / tag
    staged_release_dir.mkdir(parents=True, exist_ok=True)
    asset_output_path = staged_release_dir / args.asset_name
    upload_paths: list[Path] = []
    manifest_assets: list[dict[str, str]] = []

    if args.asset_path:
        source_asset = Path(args.asset_path)
        if not args.dry_run and not source_asset.exists():
            raise FileNotFoundError(f"Asset path not found: {source_asset}")
        print(f"Using existing asset: {source_asset}")
        if not args.dry_run:
            shutil.copy2(source_asset, asset_output_path)
    else:
        app_bundle_path = build_macos_artifact(
            binary_basename=args.binary_basename,
            app_entrypoint=args.app_entrypoint,
            dry_run=args.dry_run,
        )
        zip_macos_app(app_bundle_path=app_bundle_path, zip_output_path=asset_output_path, dry_run=args.dry_run)

    asset_digest = "0" * 64 if args.dry_run else sha256_file(asset_output_path)
    upload_paths.append(asset_output_path)
    manifest_assets.append(
        {
            "platform": args.platform,
            "name": asset_output_path.name,
            "sha256": asset_digest,
        }
    )

    for extra_asset_spec in args.extra_asset:
        platform_key, source_path = parse_extra_asset_spec(extra_asset_spec)
        if not args.dry_run and not source_path.exists():
            raise FileNotFoundError(f"Extra asset path not found: {source_path}")

        target_path = staged_release_dir / source_path.name
        print(f"Using extra asset for {platform_key}: {source_path}")
        if not args.dry_run:
            shutil.copy2(source_path, target_path)

        target_digest = "0" * 64 if args.dry_run else sha256_file(target_path)
        upload_paths.append(target_path)
        manifest_assets.append(
            {
                "platform": platform_key,
                "name": target_path.name,
                "sha256": target_digest,
            }
        )

    seen_platforms: set[str] = set()
    for item in manifest_assets:
        key = item["platform"].lower()
        if key in seen_platforms:
            raise ValueError(f"Duplicate platform specified for manifest assets: {item['platform']}")
        seen_platforms.add(key)

    notes_url = f"https://github.com/{args.updates_repo}/releases/tag/{tag}"
    manifest = build_manifest(
        version=version,
        updates_repo=args.updates_repo,
        assets=manifest_assets,
        notes_url=notes_url,
    )

    manifest_path = staged_release_dir / "latest.json"
    write_manifest_file(manifest_path, manifest, dry_run=args.dry_run)

    ensure_updates_release(repo=args.updates_repo, tag=tag, dry_run=args.dry_run)
    run_command(
        [
            "gh",
            "release",
            "upload",
            tag,
            "--repo",
            args.updates_repo,
            *[str(path) for path in upload_paths],
            str(manifest_path),
            "--clobber",
        ],
        dry_run=args.dry_run,
    )

    if args.publish_source_release and not release_exists(args.source_repo, tag):
        run_command(
            [
                "gh",
                "release",
                "create",
                tag,
                "--repo",
                args.source_repo,
                "--title",
                f"Sezzions {tag}",
                "--notes",
                f"Sezzions release {tag}",
            ],
            dry_run=args.dry_run,
        )

    if args.sync_local_main:
        sync_local_branch(args.sync_branch, dry_run=args.dry_run)

    print("\nRelease update flow completed.")
    print(f"- Version: {version}")
    print(f"- Updates repo: {args.updates_repo}")
    print(f"- Manifest URL: https://github.com/{args.updates_repo}/releases/latest/download/latest.json")
    print("- Asset URLs:")
    for asset in manifest["assets"]:
        print(f"  - {asset['platform']}: {asset['url']}")
    if args.sync_local_main:
        print(f"- Local branch synced: {args.sync_branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
