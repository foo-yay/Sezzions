from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform as host_platform
import shutil
import subprocess
import sys
from typing import Any


DEFAULT_SOURCE_REPO = "foo-yay/Sezzions"
DEFAULT_UPDATES_REPO = "foo-yay/sezzions-updates"
DEFAULT_PLATFORM_KEY = "macos-arm64"
DEFAULT_BINARY_BASENAME = "sezzions-macos-arm64"


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
    asset_name: str,
    asset_sha256: str,
    platform_key: str,
    notes_url: str,
) -> dict[str, Any]:
    tag = release_tag(version)
    return {
        "version": normalize_version(version),
        "published_at": "",  # Filled by release timestamp at upload time if needed
        "notes_url": notes_url,
        "assets": [
            {
                "platform": platform_key,
                "url": f"https://github.com/{updates_repo}/releases/download/{tag}/{asset_name}",
                "sha256": asset_sha256,
                "name": asset_name,
            }
        ],
    }


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
            app_entrypoint,
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
    parser.add_argument("--version", required=True, help="Semantic version, e.g. 1.0.1")
    parser.add_argument("--source-repo", default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--updates-repo", default=DEFAULT_UPDATES_REPO)
    parser.add_argument("--platform", default=DEFAULT_PLATFORM_KEY)
    parser.add_argument("--binary-basename", default=DEFAULT_BINARY_BASENAME)
    parser.add_argument("--app-entrypoint", default="sezzions.py")
    parser.add_argument("--asset-name", default="sezzions-macos-arm64.zip")
    parser.add_argument("--asset-path", default="", help="Use an existing zip file instead of building.")
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
    version = normalize_version(args.version)
    tag = release_tag(version)

    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI (gh) is required on PATH.")

    staged_release_dir = Path(args.release_dir) / tag
    staged_release_dir.mkdir(parents=True, exist_ok=True)
    asset_output_path = staged_release_dir / args.asset_name

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
    notes_url = f"https://github.com/{args.source_repo}/releases/tag/{tag}"
    manifest = build_manifest(
        version=version,
        updates_repo=args.updates_repo,
        asset_name=args.asset_name,
        asset_sha256=asset_digest,
        platform_key=args.platform,
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
            str(asset_output_path),
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
    print(f"- Asset URL: {manifest['assets'][0]['url']}")
    if args.sync_local_main:
        print(f"- Local branch synced: {args.sync_branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
