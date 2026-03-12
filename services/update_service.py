from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
from typing import Callable, Optional
from urllib.request import urlopen


DEFAULT_UPDATE_MANIFEST_URL = "https://github.com/foo-yay/Sezzions/releases/latest/download/latest.json"


@dataclass(frozen=True)
class UpdateAsset:
    platform: str
    url: str
    sha256: str
    name: Optional[str] = None
    size: Optional[int] = None


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: Optional[str]
    update_available: bool
    asset: Optional[UpdateAsset]
    notes_url: Optional[str] = None
    published_at: Optional[str] = None
    error: Optional[str] = None


class UpdateService:
    def __init__(
        self,
        current_version: str,
        manifest_url: str,
        platform_key: Optional[str] = None,
        fetcher: Optional[Callable[[str, int], bytes]] = None,
        timeout_seconds: int = 10,
    ) -> None:
        self.current_version = current_version
        self.manifest_url = manifest_url
        self.platform_key = platform_key or self.detect_platform_key()
        self.fetcher = fetcher or self._default_fetcher
        self.timeout_seconds = timeout_seconds

    def check_for_updates(self) -> UpdateCheckResult:
        try:
            manifest = self._fetch_manifest()
            latest_version = str(manifest["version"])
            if not self.is_newer_version(latest_version, self.current_version):
                return UpdateCheckResult(
                    current_version=self.current_version,
                    latest_version=latest_version,
                    update_available=False,
                    asset=None,
                    notes_url=manifest.get("notes_url"),
                    published_at=manifest.get("published_at"),
                )

            asset = self._select_asset_for_platform(manifest, self.platform_key)
            if asset is None:
                return UpdateCheckResult(
                    current_version=self.current_version,
                    latest_version=latest_version,
                    update_available=False,
                    asset=None,
                    notes_url=manifest.get("notes_url"),
                    published_at=manifest.get("published_at"),
                    error=f"No update asset found for platform '{self.platform_key}'",
                )

            return UpdateCheckResult(
                current_version=self.current_version,
                latest_version=latest_version,
                update_available=True,
                asset=asset,
                notes_url=manifest.get("notes_url"),
                published_at=manifest.get("published_at"),
            )
        except Exception as exc:
            return UpdateCheckResult(
                current_version=self.current_version,
                latest_version=None,
                update_available=False,
                asset=None,
                error=str(exc),
            )

    def download_and_verify(self, asset: UpdateAsset, destination_dir: Path | str) -> str:
        destination = Path(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        filename = asset.name or Path(asset.url).name or "sezzions-update.bin"
        file_path = destination / filename
        payload = self.fetcher(asset.url, self.timeout_seconds)
        file_path.write_bytes(payload)

        if not self.verify_file_checksum(file_path, asset.sha256):
            raise ValueError("Checksum mismatch for downloaded update")

        return str(file_path)

    @staticmethod
    def verify_file_checksum(file_path: Path | str, expected_sha256: str) -> bool:
        digest = sha256(Path(file_path).read_bytes()).hexdigest()
        return digest.lower() == expected_sha256.lower()

    @staticmethod
    def is_newer_version(candidate: str, current: str) -> bool:
        return UpdateService._parse_version_tuple(candidate) > UpdateService._parse_version_tuple(current)

    @staticmethod
    def detect_platform_key() -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "darwin" and machine in {"arm64", "aarch64"}:
            return "macos-arm64"
        if system == "darwin":
            return "macos-x64"
        if system == "windows":
            return "windows-x64"
        if system == "linux":
            return "linux-x64"
        return f"{system}-{machine}" if machine else system

    def _fetch_manifest(self) -> dict:
        payload = self.fetcher(self.manifest_url, self.timeout_seconds)
        manifest = json.loads(payload.decode("utf-8"))

        if "version" not in manifest:
            raise ValueError("Update manifest is missing required field 'version'")
        if "assets" not in manifest or not isinstance(manifest["assets"], list):
            raise ValueError("Update manifest is missing required list field 'assets'")
        return manifest

    @staticmethod
    def _select_asset_for_platform(manifest: dict, platform_key: str) -> Optional[UpdateAsset]:
        for item in manifest.get("assets", []):
            if str(item.get("platform", "")).lower() != platform_key.lower():
                continue

            url = item.get("url")
            checksum = item.get("sha256")
            if not url or not checksum:
                continue

            size = item.get("size")
            parsed_size = int(size) if isinstance(size, (int, str)) and str(size).isdigit() else None

            return UpdateAsset(
                platform=str(item["platform"]),
                url=str(url),
                sha256=str(checksum),
                name=item.get("name"),
                size=parsed_size,
            )
        return None

    @staticmethod
    def _parse_version_tuple(version: str) -> tuple[int, ...]:
        normalized = version.strip().lower()
        if normalized.startswith("v"):
            normalized = normalized[1:]

        if not normalized:
            return (0,)

        parts = [int(part) for part in re.findall(r"\d+", normalized)]
        if not parts:
            return (0,)
        return tuple(parts)

    @staticmethod
    def _default_fetcher(url: str, timeout: int) -> bytes:
        with urlopen(url, timeout=timeout) as response:
            return response.read()
