"""Bumps a mod's patch version when a change only players need would otherwise ship under a version already released (docs/versioning.md).

framework-update (a widened dependency range) and the Meitou compatibility watch (a lifted gameVersion cap) change what a mod's manifest
admits, which reaches players only with a new release. Each calls bump() on the manifests it changed: a manifest whose version already has a
production release (a non-prerelease GitHub release holding <Folder>-<version>.zip, as package-meitou-mod.yml names it) moves to the next
patch; a version not yet released already carries the change and stays.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def released(releases: list[dict], folder: str, version: str) -> bool:
    """Whether a production release already holds <folder>-<version>.zip."""
    asset = f"{folder}-{version}.zip"
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        if any(item.get("name") == asset for item in release.get("assets") or []):
            return True
    return False


def next_patch(version: str) -> str | None:
    match = VERSION.match(version)
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def bump(manifest_path: Path, releases: list[dict], notes: list[str]) -> str | None:
    """Moves the manifest to the next patch when its version is already released; returns the new version, or None when it stays."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = manifest.get("version", "")
    if not released(releases, manifest_path.parent.name, version):
        return None
    bumped = next_patch(version)
    if bumped is None:
        return None
    manifest["version"] = bumped
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    notes.append(f"- `{manifest.get('id')}` `{version}` → `{bumped}` ({version} is released, so the change ships as a new patch)")
    return bumped
